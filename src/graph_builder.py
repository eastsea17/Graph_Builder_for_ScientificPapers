
import pandas as pd
import os
import glob
from itertools import combinations
import numpy as np
import logging
from ollama_client import OllamaClient

class GraphBuilder:
    def __init__(self, config):
        self.config = config
        self.output_dir = config['output_dir']
        self.similarity_enabled = config['similarity']['enabled']
        self.similarity_threshold = config['similarity']['threshold']
        if self.similarity_enabled:
            self.client = OllamaClient(config)

    def build_graph(self, extraction_results):
        os.makedirs(self.output_dir, exist_ok=True)
        
        papers = []
        relations = []
        
        # Entity collections: { text: { 'id': text, 'label': text, 'type': TYPE } }
        # Using text as ID for simplicity as per example
        entities_background = {}
        entities_purpose = {}
        entities_methodology = {}
        entities_results = {}
        
        all_entities_text = [] # For similarity
        
        for record in extraction_results:
            p_id = record['paper_id']
            full_text = record['full_text']
            # Label is truncated text
            p_label = (full_text[:50] + '...') if len(full_text) > 50 else full_text
            
            papers.append({
                'Id': p_id,
                'Label': p_label, 
                'Type': 'Paper',
                'Full_Text': full_text
            })
            
            ext = record['extracted']
            if not ext:
                continue
                
            # Process each category
            # Background
            for item in ext.get('background', []):
                clean_item = item.strip()
                if not clean_item: continue
                entities_background[clean_item] = {'Id': clean_item, 'Label': clean_item, 'Type': 'Background'}
                relations.append({'Source': p_id, 'Target': clean_item, 'Type': 'HAS_BACKGROUND', 'Weight': 1.0})
                all_entities_text.append({'text': clean_item, 'type': 'Background'})

            # Purpose
            for item in ext.get('purpose', []):
                clean_item = item.strip()
                if not clean_item: continue
                entities_purpose[clean_item] = {'Id': clean_item, 'Label': clean_item, 'Type': 'Purpose'}
                relations.append({'Source': p_id, 'Target': clean_item, 'Type': 'HAS_PURPOSE', 'Weight': 1.0})
                all_entities_text.append({'text': clean_item, 'type': 'Purpose'})

            # Methodology
            for item in ext.get('methodology', []):
                clean_item = item.strip()
                if not clean_item: continue
                entities_methodology[clean_item] = {'Id': clean_item, 'Label': clean_item, 'Type': 'Methodology'}
                relations.append({'Source': p_id, 'Target': clean_item, 'Type': 'HAS_METHODOLOGY', 'Weight': 1.0})
                all_entities_text.append({'text': clean_item, 'type': 'Methodology'})

            # Results
            for item in ext.get('results', []):
                clean_item = item.strip()
                if not clean_item: continue
                entities_results[clean_item] = {'Id': clean_item, 'Label': clean_item, 'Type': 'Results'}
                relations.append({'Source': p_id, 'Target': clean_item, 'Type': 'HAS_RESULTS', 'Weight': 1.0})
                all_entities_text.append({'text': clean_item, 'type': 'Results'})

        # Save Papers
        pd.DataFrame(papers).to_csv(os.path.join(self.output_dir, 'papers.csv'), index=False)
        
        # Save Entities
        pd.DataFrame(list(entities_background.values())).to_csv(os.path.join(self.output_dir, 'research_background.csv'), index=False)
        pd.DataFrame(list(entities_purpose.values())).to_csv(os.path.join(self.output_dir, 'research_purpose.csv'), index=False)
        pd.DataFrame(list(entities_methodology.values())).to_csv(os.path.join(self.output_dir, 'research_methodology.csv'), index=False)
        pd.DataFrame(list(entities_results.values())).to_csv(os.path.join(self.output_dir, 'research_resultsandeffects.csv'), index=False)
        
        # Similarity
        if self.similarity_enabled and len(all_entities_text) > 0:
            print("Computing similarities (this might take a while)...")
            # Get unique texts to embed
            unique_texts = list(set([x['text'] for x in all_entities_text]))
            
            # Embed all unique texts
            # We can use batching if the list is huge, but let's do simple loop for now
            embeddings = {}
            for text in unique_texts:
                emb = self.client.embed(text)
                if emb:
                    embeddings[text] = emb
            
            # Compute similarity
            # Create a matrix
            text_list = list(embeddings.keys())
            if len(text_list) > 1:
                mat = np.array([embeddings[t] for t in text_list])
                
                # Normalize
                norm = np.linalg.norm(mat, axis=1, keepdims=True)
                # Avoid div by zero
                norm[norm == 0] = 1.0
                normalized_mat = mat / norm
                
                sim_matrix = np.dot(normalized_mat, normalized_mat.T)
                
                # Extract pairs > threshold
                # Only upper triangle to avoid duplicates
                rows, cols = np.where(np.triu(sim_matrix, k=1) > self.similarity_threshold)
                
                for r, c in zip(rows, cols):
                    score = float(sim_matrix[r, c])
                    src = text_list[r]
                    tgt = text_list[c]
                    relations.append({
                        'Source': src,
                        'Target': tgt,
                        'Type': 'RELATED_TO',
                        'Weight': score
                    })

        # Save Relations
        pd.DataFrame(relations).to_csv(os.path.join(self.output_dir, 'relations.csv'), index=False)
        print("Graph construction complete.")
