import os
import json
import chromadb
from dotenv import load_dotenv
from google import genai
from google.genai import types

class RagMemory:
    def __init__(self):
        load_dotenv()
        # inicia o cliente gemini 
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model_id = 'gemini-2.5-flash'
        
        self.chroma_client = chromadb.PersistentClient(path="./vectorstore")
        
        # cria ou carrega a coleção onde vai guardar as memórias
        # ChromaDB usa internamente modelo sentence-transformers por defeito
        self.collection = self.chroma_client.get_or_create_collection(
            name="retail_inspections"
        )
        print("[LOG] Sistema de Memória (RAG) iniciado com sucesso.")

    def generate_rich_summary(self, inspection_data: dict) -> str:
        
        prompt = f"""
        Atua como um arquivista de uma loja de retalho. 
        Abaixo estão os dados JSON estruturados de uma inspeção a uma prateleira.
        
        A tua tarefa é escrever um parágrafo denso e descritivo (máximo 4 linhas) que resuma o que foi encontrado.
        Não uses formatação (sem negritos nem listas). Menciona especificamente:
        - A zona da loja
        - O estado global (ok, warning, critical)
        - Detalhes visuais dos produtos, percentagens (fill rate) e anomalias detetadas, se existirem.
        
        Dados da Inspeção:
        {json.dumps(inspection_data, ensure_ascii=False)}
        """
        
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=[prompt],
                config=types.GenerateContentConfig(temperature=0.0)
            )
            return response.text.strip()
        except Exception as e:
            return f"Erro ao gerar sumário: {str(e)}"

    def index_inspection(self, inspection_data: dict):
        #guarda o sumário textual e os metadados
        
        inspection_id = inspection_data.get("inspection_id")
        
        print(f"[LOG] A gerar sumário para a inspeção {inspection_id}.")
        summary_text = self.generate_rich_summary(inspection_data)
        print(f"[LOG] Sumário gerado: {summary_text}")
        
        # prepara os metadados (para filtrar por zona/status mais tarde)
        metadata = {
            "zone_id": inspection_data.get("zone_id", "unknown"),
            "timestamp": inspection_data.get("timestamp", ""),
            "overall_status": inspection_data.get("overall_status", "unknown")
        }
        
        # guarda no ChromaDB
        self.collection.upsert(
            documents=[summary_text],
            metadatas=[metadata],
            ids=[inspection_id]
        )
        print(f"[LOG] Inspeção {inspection_id} indexada no ChromaDB com sucesso.\n")

    
    def query_memory(self, user_question: str, n_results: int = 3) -> str:
        #procura o histórico e responde à pergunta do gestor baseando-se apenas nos dados recuperados
        
        print(f"[LOG] A pesquisar na memória por: '{user_question}'.")
        
        #recuperar Top-K
        # chromaDB converte automaticamente a pergunta num embedding e faz a similaridade de cosseno
        results = self.collection.query(
            query_texts=[user_question],
            n_results=n_results
        )
        
        # construir o texto de contexto com os resultados recuperados
        context_blocks = []
        # verifica se encontrou documentos
        if results['documents'] and len(results['documents'][0]) > 0:
            for i in range(len(results['documents'][0])):
                doc = results['documents'][0][i]
                meta = results['metadatas'][0][i]
                ins_id = results['ids'][0][i]
                context_blocks.append(f"- ID: {ins_id} | Data: {meta.get('timestamp')} | Zona: {meta.get('zone_id')}\n  Resumo: {doc}")
                
        context_text = "\n\n".join(context_blocks)
        
        if not context_text:
            return "Não encontrei registos históricos no sistema para responder a essa pergunta."

        print(f"[LOG] Contexto recuperado da base de dados:\n{context_text}\n")

        # responder com base apenas neste contexto
        prompt = f"""
        Atua como um assistente analítico de retalho.
        Usa APENAS o contexto histórico recuperado abaixo para responder à pergunta do gestor.
        
        REGRA OBRIGATÓRIA: Tens de referenciar explicitamente o ID da inspeção e a data quando mencionares um evento recuperado.
        
        Contexto Histórico Recuperado:
        {context_text}
        
        Pergunta do Gestor: {user_question}
        """
        
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=[prompt],
                config=types.GenerateContentConfig(temperature=0.0)
            )
            return response.text.strip()
        except Exception as e:
            return f"Erro ao gerar a resposta: {str(e)}"

# bloco de teste
if __name__ == "__main__":
    memory = RagMemory()
    
    # testar uma pergunta em linguagem natural 
    pergunta = "Qual é o estado atual das prateleiras de Sprite na zona Z_S2?"
    
    resposta = memory.query_memory(pergunta, n_results=1)

    print("RESPOSTA DO SISTEMA RAG:")
    print(resposta)
    