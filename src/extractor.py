import pandas as pd
import json
import logging
from tqdm import tqdm
from pydantic import BaseModel, Field, ValidationError
from typing import List, Optional
from ollama_client import OllamaClient  # Fixed import path

# 1. Pydantic 모델 정의: LLM이 뱉어야 할 정확한 구조
class PaperExtraction(BaseModel):
    background: List[str] = Field(
        default_factory=list, 
        description="연구의 배경, 기존 연구의 한계점, 또는 이 연구가 필요한 이유 (Problem statement & Gap)"
    )
    purpose: List[str] = Field(
        default_factory=list, 
        description="이 논문이 제안하는 핵심 아이디어, 주된 연구 목표, 또는 해결하고자 하는 구체적인 과제 (Main contribution & Objective)"
    )
    methodology: List[str] = Field(
        default_factory=list, 
        description="제안된 모델, 사용된 알고리즘, 데이터셋, 실험 환경 등 구체적인 연구 방법 (Specific methods, models, datasets)"
    )
    results: List[str] = Field(
        default_factory=list, 
        description="실험 결과, 달성한 성능 수치(SOTA 달성 등), 정량적/정성적 효과 및 결론 (Key findings, metrics, and conclusion)"
    )

class Extractor:
    def __init__(self, config):
        self.config = config
        self.client = OllamaClient(config)
        
        # Pydantic 스키마
        schema_json = json.dumps(PaperExtraction.model_json_schema(), indent=2)
        
        # config.yaml에서 프롬프트 가져오기 (없으면 기본값 사용)
        config_prompt = config.get('extraction', {}).get('system_prompt', "")
        
        if config_prompt:
             # config에 있는 프롬프트에 스키마만 덧붙여서 사용
            self.base_system_prompt = f"{config_prompt}\n\nSchema:\n```json\n{schema_json}\n```"
        else:
            # 개선된 시스템 프롬프트 (Default)
            self.base_system_prompt = (
                "You are an expert scientific researcher specializing in literature review. "
                "Your task is to analyze the given paper abstract and extract structured information.\n\n"
                
                "### Guidelines:\n"
                "1. **Analyze Context**: Read the entire abstract to understand the flow from problem to solution.\n"
                "2. **Identify Sections**: Look for keywords like 'We propose', 'However', 'Experiments show', etc.\n"
                "3. **Be Specific**: Do not use vague phrases. Extract specific model names, metrics, and finding details.\n"
                "4. **Format**: Return the result strictly as a valid JSON object following the schema below.\n\n"
                
                f"### Output Schema:\n```json\n{schema_json}\n```\n\n"
                
                "### Rules:\n"
                "- Extract 1-3 concise key points for each category.\n"
                "- If information is missing for a category, leave it as an empty list.\n"
                "- **Use English for the values.** (한국어로 추출하려면 이 부분을 'Use Korean'으로 변경)\n"
                "- Do not include any explanation or markdown outside the JSON block."
            )

    def process_csv(self, file_path):
        try:
            df = pd.read_csv(file_path)
            
            # 1. Config에서 컬럼명 확인
            target_col = self.config.get('abstract_col')
            abstract_col = None

            if target_col and target_col in df.columns:
                abstract_col = target_col
                print(f"Using configured column: '{abstract_col}'")
            else:
                # 2. Config에 없거나 잘못된 경우, 자동으로 찾기 (Case-insensitive 'abstract')
                logging.info(f"Configured column '{target_col}' not found. Attempting auto-detection...")
                for col in df.columns:
                    if 'abstract' in col.lower():
                        abstract_col = col
                        break
                # 3. 그래도 없으면 첫 번째 컬럼 사용
                if not abstract_col:
                    abstract_col = df.columns[0]
                    logging.warning(f"No 'abstract' column found. Defaulting to first column: '{abstract_col}'")
                 
            print(f"Processing {len(df)} records with Structured Extraction (Column: {abstract_col})...")
            
            results = []
            
            for index, row in tqdm(df.iterrows(), total=len(df)):
                abstract = row[abstract_col]
                if pd.isna(abstract) or str(abstract).strip() == "":
                    continue

                extracted_data = self._extract_from_text(str(abstract))
                
                if extracted_data:
                    record = {
                        'paper_id': f"Paper_{index+1}",
                        'full_text': str(abstract),
                        'extracted': extracted_data.model_dump() # Pydantic 모델을 dict로 변환
                    }
                    results.append(record)
            
            return results

        except Exception as e:
            logging.error(f"Error processing CSV: {e}")
            return []

    def _extract_from_text(self, text) -> Optional[PaperExtraction]:
        # JSON validation enabled in generate by default/implicit
        response_str = self.client.generate(text, self.base_system_prompt)
        if not response_str:
            return None
        
        try:
            # 1. JSON 문자열 파싱 시도 (백틱 제거 등 전처리)
            clean_str = response_str.strip()
            if "```json" in clean_str:
                import re
                match = re.search(r'```json\s*({.*?})\s*```', clean_str, re.DOTALL)
                if match:
                    clean_str = match.group(1)
            elif "{" in clean_str:
                 # 가장 바깥쪽 중괄호 찾기
                start = clean_str.find("{")
                end = clean_str.rfind("}") + 1
                clean_str = clean_str[start:end]

            # 2. Pydantic을 사용한 유효성 검사 (Validation)
            # JSON 파싱 + 스키마 검증을 동시에 수행
            data = PaperExtraction.model_validate_json(clean_str)
            return data

        except (json.JSONDecodeError, ValidationError) as e:
            logging.warning(f"Validation failed for abstract snippet: {text[:30]}... Error: {e}")
            # 필요한 경우 여기서 재시도(Retry) 로직을 구현할 수 있습니다.
            return None
