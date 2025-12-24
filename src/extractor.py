import pandas as pd
import json
import logging
from tqdm import tqdm
from pydantic import BaseModel, Field, ValidationError
from typing import List, Optional
from ollama_client import OllamaClient  # Fixed import path

# 1. Pydantic 모델 정의: LLM이 뱉어야 할 정확한 구조
class PaperExtraction(BaseModel):
    background: List[str] = Field(default_factory=list, description="연구 배경 및 필요성 핵심 요약 (1-3 items)")
    purpose: List[str] = Field(default_factory=list, description="연구의 구체적인 목적 및 목표 (1-3 items)")
    methodology: List[str] = Field(default_factory=list, description="사용된 기술, 모델, 알고리즘, 데이터셋 등 방법론 (1-3 items)")
    results: List[str] = Field(default_factory=list, description="연구 결과, 성과, 성능 지표, 효과 (1-3 items)")

class Extractor:
    def __init__(self, config):
        self.config = config
        self.client = OllamaClient(config)
        
        # Pydantic 스키마를 프롬프트에 주입하여 구조화된 출력을 유도
        schema_json = json.dumps(PaperExtraction.model_json_schema(), indent=2)
        self.base_system_prompt = (
            "You are an expert scientific researcher. Extract structured information from the paper abstract.\n"
            "You MUST return a valid JSON object strictly following this schema:\n"
            f"```json\n{schema_json}\n```\n"
            "Rules:\n"
            "- Extract concise key points for each category.\n"
            "- Use English for the values.\n"
            "- Do not include any text outside the JSON block."
        )

    def process_csv(self, file_path):
        try:
            df = pd.read_csv(file_path)
            # Find abstract column case-insensitively or by position
            abstract_col = None
            for col in df.columns:
                if 'abstract' in col.lower():
                    abstract_col = col
                    break
            if not abstract_col:
                 abstract_col = df.columns[0] # Fallback to first column
                 
            print(f"Processing {len(df)} records with Structured Extraction...")
            
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
