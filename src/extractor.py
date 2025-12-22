
import pandas as pd
import json
import logging
from tqdm import tqdm
from ollama_client import OllamaClient

class Extractor:
    def __init__(self, config):
        self.config = config
        self.client = OllamaClient(config)
        self.system_prompt = config['extraction']['system_prompt']

    def process_csv(self, file_path):
        try:
            df = pd.read_csv(file_path)
            if 'abstract' not in df.columns:
                # Fallback: assume first column
                df.rename(columns={df.columns[0]: 'abstract'}, inplace=True)
            
            results = []
            
            # Limit for testing if needed, but processing all for now
            # You might want to process a subset for "fast" demo if the file is huge
            # But the user asked for the code to do it.
            
            print(f"Processing {len(df)} records...")
            
            for index, row in tqdm(df.iterrows(), total=len(df)):
                abstract = row['abstract']
                if pd.isna(abstract) or str(abstract).strip() == "":
                    continue

                extracted_data = self._extract_from_text(abstract)
                
                if extracted_data:
                    record = {
                        'paper_id': f"Paper_{index+1}",
                        'full_text': abstract,
                        'extracted': extracted_data
                    }
                    results.append(record)
            
            return results

        except Exception as e:
            logging.error(f"Error processing CSV: {e}")
            return []

    def _extract_from_text(self, text):
        response_str = self.client.generate(text, self.system_prompt)
        if not response_str:
            return None
        
        try:
            # Robust extraction of JSON part
            import re
            # pattern for ```json ... ``` or just { ... }
            # We look for the first { and the last }
            clean_str = response_str.strip()
            
            # If wrapped in code blocks, try to extract content inside
            match = re.search(r'```json\s*({.*?})\s*```', clean_str, re.DOTALL)
            if match:
                clean_str = match.group(1)
            else:
                # If not explicitly marked, try to find the outer braces
                match = re.search(r'({.*})', clean_str, re.DOTALL)
                if match:
                    clean_str = match.group(1)
            
            data = json.loads(clean_str)
            return data
        except (json.JSONDecodeError, AttributeError):
            logging.error(f"Failed to parse JSON response. Response preview: {response_str[:100]}...")
            return None
