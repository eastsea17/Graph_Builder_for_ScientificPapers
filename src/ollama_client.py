
import ollama
import logging

class OllamaClient:
    def __init__(self, config):
        self.config = config
        self.base_url = config['ollama']['base_url']
        # The ollama python client uses OLLAMA_HOST env var, or defaults to localhost:11434. 
        # If the user has a custom URL in config, we might need to set it, 
        # but usually the client creates a Client object.
        self.client = ollama.Client(host=self.base_url)
        self.models = config['ollama']['models']
        self.selected_model_key = config['ollama']['selected_model']
        self.model = self.models.get(self.selected_model_key, self.selected_model_key)
        
        logging.info(f"Initialized OllamaClient with model: {self.model}")

    def generate(self, prompt, system_prompt=None):
        try:
            messages = []
            if system_prompt:
                messages.append({'role': 'system', 'content': system_prompt})
            messages.append({'role': 'user', 'content': prompt})

            response = self.client.chat(model=self.model, messages=messages, format='json')
            return response['message']['content']
        except Exception as e:
            logging.error(f"Error generating response from Ollama: {e}")
            return None

    def embed(self, text):
        try:
            mod = self.config['similarity']['embedding_model']
            response = self.client.embeddings(model=mod, prompt=text)
            return response['embedding']
        except Exception as e:
            logging.error(f"Error generating embedding: {e}")
            # Fallback or return None
            return None
