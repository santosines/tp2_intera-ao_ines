import os
from pathlib import Path

try:
    from datasets import load_dataset
except ImportError:
    print("ERRO: A biblioteca 'datasets' não está instalada.")
    print("Por favor, executa no terminal: pip install datasets")
    exit()

def download_huggingface_sample(num_images=300):
    raw_dir = Path("data/raw_hf_images")
    raw_dir.mkdir(parents=True, exist_ok=True)
    
    print("A ligar aos servidores do HuggingFace.")
    
    try:
        dataset = load_dataset("benjamintli/sku110k", split="train")
        
        success_count = 0
        print("\nA descarregar e a guardar as imagens localmente.")
        
        for i, item in enumerate(dataset):
            if success_count >= num_images:
                break
            
            image = item['image']
            
            # converter para RGB caso alguma imagem tenha transparências
            if image.mode != 'RGB':
                image = image.convert('RGB')
                
            # guardar na pasta
            save_path = raw_dir / f"sku_img_{i}.jpg"
            image.save(save_path)
            success_count += 1
            
            if success_count % 50 == 0:
                print(f"Guardadas: {success_count}/{num_images} imagens.")
                
        print(f"\nConcluído. {success_count} imagens descarregadas com sucesso.")
        print(f"Imagens na pasta: {raw_dir}")
        
    except Exception as e:
        print(f"\nErro ao descarregar o dataset: {str(e)}")

if __name__ == "__main__":
    download_huggingface_sample(300)