import pandas as pd
import os
import numpy as np
import logging
from collections import defaultdict
from ollama_client import OllamaClient # Fixed import path
import networkx as nx  # 군집화(Connected Components)를 위해 사용

class EntityResolver:
    """
    유사한 엔티티를 찾아 하나의 정규화된 이름(Canonical Name)으로 병합하는 클래스
    """
    def __init__(self, client: OllamaClient, threshold=0.85):
        self.client = client
        self.threshold = threshold
        self.cache = {} # Embedding cache

    def resolve(self, entities: list, entity_type: str) -> dict:
        """
        Input: ['CNN', 'ConvNet', 'SVM']
        Output: {'CNN': 'Convolutional Neural Network', 'ConvNet': 'Convolutional Neural Network', 'SVM': 'SVM'}
        """
        unique_entities = list(set([e.strip() for e in entities if e.strip()]))
        if not unique_entities:
            return {}
        
        logging.info(f"Resolving {len(unique_entities)} {entity_type} entities...")

        # 1. Embeddings 계산
        embeddings = {}
        valid_entities = []
        for text in unique_entities:
            emb = self.client.embed(text)
            if emb:
                embeddings[text] = np.array(emb)
                valid_entities.append(text)
        
        if not valid_entities:
            return {e: e for e in unique_entities}

        # 2. Similarity Matrix 계산
        matrix = np.array([embeddings[e] for e in valid_entities])
        # Normalize
        norm = np.linalg.norm(matrix, axis=1, keepdims=True)
        norm[norm == 0] = 1e-10
        normalized_matrix = matrix / norm
        cosine_sim = np.dot(normalized_matrix, normalized_matrix.T)

        # 3. Graph 기반 군집화 (NetworkX 사용)
        g = nx.Graph()
        g.add_nodes_from(valid_entities)
        
        # 임계값 넘는 쌍 연결
        rows, cols = np.where(np.triu(cosine_sim, k=1) > self.threshold)
        for r, c in zip(rows, cols):
            g.add_edge(valid_entities[r], valid_entities[c])

        # 4. 각 군집(Cluster)별 정규화 수행
        mapping = {}
        
        # 연결된 컴포넌트(유사한 엔티티 그룹) 찾기
        clusters = list(nx.connected_components(g))
        
        logging.info(f"Found {len(clusters)} unique semantic clusters.")
        
        from tqdm import tqdm
        for cluster in tqdm(clusters, desc=f"Resolving {entity_type} clusters"):
            cluster_list = list(cluster)
            
            if len(cluster_list) == 1:
                # 유사한 게 없으면 그대로 사용
                mapping[cluster_list[0]] = cluster_list[0]
            else:
                # 유사한 게 여러 개면 LLM에게 표준 용어 질문
                canonical = self._get_canonical_name(cluster_list, entity_type)
                for item in cluster_list:
                    mapping[item] = canonical
                    
        return mapping

    def _get_canonical_name(self, terms, entity_type):
        # 이미 처리한 적 있으면 캐시 사용 (선택 사항)
        # LLM에게 가장 일반적인 용어 선택 요청
        prompt = (
            f"You are a scientific terminology expert. I have a list of similar terms referring to the same concept in {entity_type}.\n"
            f"Terms: {terms}\n"
            "Identify the single most standard, full, and canonical scientific name from this list (or a better standard name if obvious).\n"
            "Return ONLY the canonical name string. No explanation."
        )
        
        try:
            # LLM 호출 (JSON 모드 아님, 단순 텍스트)
            # Pass json_format=False to force text output
            response = self.client.generate(prompt, json_format=False)
            canonical = response.strip().strip('"').strip("'")
            # 만약 이상한 응답이면 리스트 중 가장 긴 것 or 첫 번째 것 선택
            if len(canonical) > 50 or '\n' in canonical:
                return sorted(terms, key=len, reverse=True)[0]
            return canonical
        except:
            return terms[0]


class GraphBuilder:
    def __init__(self, config):
        self.config = config
        self.output_dir = config['output_dir']
        self.client = OllamaClient(config)
        
        # Config에서 해상도(Resolution) 활성화 여부 확인 (기본값 True)
        self.resolution_enabled = config.get('graph', {}).get('entity_resolution', True)
        self.resolver = EntityResolver(self.client, threshold=0.90) if self.resolution_enabled else None

    def build_graph(self, extraction_results):
        os.makedirs(self.output_dir, exist_ok=True)
        
        papers = []
        raw_relations = []
        
        # 1. 모든 엔티티 수집 (타입별)
        all_entities_by_type = defaultdict(list)
        
        logging.info(f"Building graph from {len(extraction_results)} records...")
        
        # 논문 노드 먼저 생성
        for record in extraction_results:
            p_id = record['paper_id']
            full_text = record['full_text']
            p_label = (full_text[:50] + '...') if len(full_text) > 50 else full_text
            
            papers.append({
                'Id': p_id,
                'Label': p_label, 
                'Type': 'Paper',
                'Full_Text': full_text
            })
            
            ext = record['extracted'] # 이미 dict 형태 (Pydantic model_dump 결과)
            if not ext: continue

            for cat in ['background', 'purpose', 'methodology', 'results']:
                items = ext.get(cat, [])
                for item in items:
                    if item:
                        all_entities_by_type[cat].append(item)
                        # 임시 관계 저장 (나중에 정규화된 이름으로 교체)
                        raw_relations.append({
                            'Source': p_id, 
                            'Original_Target': item, 
                            'Rel_Type': f'HAS_{cat.upper()}'
                        })

        # 2. Entity Resolution 수행 (유사 엔티티 병합)
        # Mapping: { 'Original Text' : 'Canonical ID' }
        global_mapping = {}
        
        if self.resolution_enabled:
            logging.info("--- Starting Entity Resolution ---")
            for cat, items in all_entities_by_type.items():
                if not items: continue
                # 카테고리별로 리졸브 수행 (Methodology끼리, Result끼리 섞이지 않도록)
                cat_map = self.resolver.resolve(items, cat)
                global_mapping.update(cat_map)
        else:
            # Resolution 안 하면 그대로 매핑
            for items in all_entities_by_type.values():
                for item in items:
                    global_mapping[item] = item

        # 3. 최종 노드 및 엣지 생성
        final_entities = {} # { 'Canonical Name': {Node Data} }
        final_relations = []

        # 엔티티 노드 생성
        for original_text, canonical_name in global_mapping.items():
            # 어떤 카테고리인지 역추적 (단순화를 위해 마지막 발견된 타입 사용하거나 복합 타입 처리)
            # 여기서는 Node 생성 시점 중복 제거
            if canonical_name not in final_entities:
                final_entities[canonical_name] = {
                    'Id': canonical_name,
                    'Label': canonical_name,
                    'Type': 'Entity' # 혹은 세부 타입
                }
        
        # 관계 엣지 생성 (Source -> Canonical Target)
        for rel in raw_relations:
            orig = rel['Original_Target']
            if orig in global_mapping:
                canonical = global_mapping[orig]
                final_relations.append({
                    'Source': rel['Source'],
                    'Target': canonical,
                    'Type': rel['Rel_Type'],
                    'Weight': 1.0
                })

        # 4. 파일 저장
        logging.info("Saving graph nodes and edges...")
        if papers:
             pd.DataFrame(papers).to_csv(os.path.join(self.output_dir, 'papers.csv'), index=False)
        else:
             logging.warning("No papers processed.")
             
        if final_entities:
            pd.DataFrame(list(final_entities.values())).to_csv(os.path.join(self.output_dir, 'entities.csv'), index=False)
        else:
            logging.warning("No entities found.")
            
        if final_relations:
            pd.DataFrame(final_relations).to_csv(os.path.join(self.output_dir, 'relations.csv'), index=False)
        else:
            logging.warning("No relations found.")
        
        logging.info("Graph construction complete with Entity Resolution.")
