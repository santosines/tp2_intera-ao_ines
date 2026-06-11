import os
import json
import time
import hashlib
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

# carregar a chave da API do ficheiro .env
load_dotenv()

class ShelfInspector:
    def __init__(self):
        # iniciar o cliente com a chave que está no .env
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        
        self.model_id = 'gemini-2.5-flash'
        
        self.cache_dir = Path("cache")
        self.cache_dir.mkdir(exist_ok=True)
        
        # limites da API (15 req/min) - 4.1 segundos entre requests
        self.last_request_time = 0
        self.min_interval = 4.1 

    def _get_image_hash(self, image_path: str) -> str:
        hasher = hashlib.md5()
        with open(image_path, 'rb') as f:
            buf = f.read()
            hasher.update(buf)
        return hasher.hexdigest()

    def _check_cache(self, image_hash: str, strategy: str):
        cache_file = self.cache_dir / f"{image_hash}_{strategy}.json"
        if cache_file.exists():
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    def _save_cache(self, image_hash: str, strategy: str, data: dict):
        cache_file = self.cache_dir / f"{image_hash}_{strategy}.json"
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def _rate_limit(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_request_time = time.time()

    def inspect_image(self, image_path: str, zone_id: str, strategy: str = "strategy_a_zeroshot") -> dict:
        img_hash = self._get_image_hash(image_path)
        
        # verificar cache
        cached_result = self._check_cache(img_hash, strategy)
        if cached_result:
            print("Resultado recuperado da cache.")
            # atualizar os IDs para cada chamada parecer única
            cached_result["inspection_id"] = f"INS_{time.strftime('%Y%m%d_%H%M%S')}"
            cached_result["timestamp"] = time.strftime('%Y-%m-%dT%H:%M:%SZ')
            return cached_result

        # carregar o prompt
        prompt_file = Path(f"prompts/{strategy}.txt")
        if not prompt_file.exists():
            return {"error": f"Ficheiro de prompt não encontrado: {prompt_file}"}
            
        with open(prompt_file, 'r', encoding='utf-8') as f:
            prompt_text = f.read()

        # chamar a API usando a nova biblioteca
        print(f"A analisar a imagem {image_path} no Gemini.")
        self._rate_limit()
        
        try:
            image_file = self.client.files.upload(file=image_path)
            
            # lógica de backoff exponencial 
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = self.client.models.generate_content(
                        model=self.model_id,
                        contents=[image_file, prompt_text],
                        config=types.GenerateContentConfig(
                            temperature=0.0,
                            response_mime_type="application/json"
                        )
                    )
                    break # ee tiver sucesso, sai do loop de tentativas
                except Exception as api_error:
                    if "429" in str(api_error) and attempt < max_retries - 1:
                        wait_time = (2 ** attempt) * 10
                        print(f"      [AVISO] Limite de API (429). A aguardar {wait_time}s antes de tentar de novo.")
                        time.sleep(wait_time)
                    else:
                        raise api_error # se não for 429 ou esgotar tentativas, levanta o erro normal
            
            result_data = json.loads(response.text)
            result_data["inspection_id"] = f"INS_{time.strftime('%Y%m%d_%H%M%S')}"
            result_data["timestamp"] = time.strftime('%Y-%m-%dT%H:%M:%SZ')
            result_data["image_path"] = image_path
            result_data["zone_id"] = zone_id

            # guardar na cache
            self._save_cache(img_hash, strategy, result_data)
            return result_data
            
        except Exception as e:
            return {"error": f"Erro na API do Gemini: {str(e)}"}

# bloco de teste
if __name__ == "__main__":
    inspector = ShelfInspector()
    resultado = inspector.inspect_image("data/images/avaliacao_15/exemplo1.jpg", "Z_S2", "strategy_a_zeroshot")
    print(json.dumps(resultado, indent=4, ensure_ascii=False))