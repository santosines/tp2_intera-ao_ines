import os
import json
import time
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

class ReportGenerator:
    def __init__(self):
        load_dotenv()
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model_id = 'gemini-2.5-flash'
        
        self.reports_dir = Path("data/inspections")
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def generate_markdown_report(self, session_inspections: list, triggered_alerts: list, rag_context: str) -> str:
        #pede ao LLM para compilar os dados num relatório Markdown formatado
        print("[LOG] A iniciar a geração do relatório com o LLM.")
        
        # converte as listas para JSON text para o LLM ler
        inspections_text = json.dumps(session_inspections, ensure_ascii=False, indent=2)
        alerts_text = json.dumps(triggered_alerts, ensure_ascii=False, indent=2)
        
        prompt = f"""
        Atua como um analista de dados de retalho. A tua tarefa é compilar um 'Inspection Report' profissional em formato Markdown.
        
        Deves basear o relatório EXCLUSIVAMENTE nos seguintes dados que foram recolhidos hoje:
        
        1. DADOS DAS INSPEÇÕES:
        {inspections_text}
        
        2. ALERTAS DAS REGRAS DISPARADAS:
        {alerts_text}
        
        3. CONTEXTO HISTÓRICO (RAG):
        {rag_context}
        
        ---
        
        DIRETRIZES DE FORMATAÇÃO OBRIGATÓRIAS (Tens de incluir exatamente estas 6 secções):
        
        # 1. Sumário executivo
        Máximo 150 palavras. Resume o estado geral da loja nesta sessão. Quantas zonas foram inspecionadas, quantos problemas críticos e quantos warnings. Usa linguagem direta.
        
        # 2. Problemas por zona
        Para cada zona com problemas: lista os problemas, a severidade e o fill rate. Se não houver problemas, indica que as zonas estão conformes.
        
        # 3. Regras disparadas
        Que regras foram ativadas, que dados as ativaram e a mensagem gerada. Se nenhuma regra disparou, indica-o.
        
        # 4. Contexto histórico relevante
        Menciona padrões passados recuperados do RAG com referências EXPLÍCITAS aos IDs das inspeções passadas (inspection_id) e às datas.
        
        # 5. Recomendações
        Máximo de 5 ações concretas, ordenadas por urgência. Cada ação deve ser específica o suficiente para a equipa da loja executar.
        
        # 6. Integração com trajectória
        (Como os dados de trajectória não estão disponíveis nesta sessão, adiciona uma breve nota a referir que a correlação de afluência de clientes não pôde ser calculada para esta inspeção).
        """
        
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=[prompt],
                config=types.GenerateContentConfig(temperature=0.0)
            )
            return response.text.strip()
        except Exception as e:
            return f"Erro ao gerar relatório: {str(e)}"

    def save_report(self, markdown_content: str, session_id: str = None) -> str:
        #guarda o relatório na pasta data/inspections
        if session_id is None:
            session_id = f"SESSION_{time.strftime('%Y%m%d_%H%M%S')}"
            
        file_path = self.reports_dir / f"report_{session_id}.md"
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
            
        print(f"[LOG] Relatório guardado com sucesso em: {file_path}")
        return str(file_path)

#bloco de teste
if __name__ == "__main__":
    generator = ReportGenerator()
    
    #simular os dados de entrada para o teste
    # 1. Uma inspeção simulada (como se viesse do shelf_inspector)
    mock_inspections = [
        {
            "inspection_id": "INS_TEST_TODAY",
            "zone_id": "Z_S2",
            "overall_status": "warning",
            "issues": [
                {
                    "type": "empty_shelf",
                    "location": "prateleira inferior",
                    "severity": "medium",
                    "shelf fill rate": 0.60
                }
            ]
        }
    ]
    
    # 2. Um alerta simulado (como se viesse do rule_engine)
    mock_alerts = [
        {
            "rule_id": "RULE_123",
            "alert_level": "warning",
            "message": "[WARNING] Alerta de prateleira vazia na zona Z_S2",
            "triggered_by_issues": ["ISS_001"]
        }
    ]
    
    # 3. Contexto histórico simulado (como se viesse do rag_memory)
    mock_rag = "ID: INS_20260610_223629 | Data: 2026-06-10 | A zona Z_S2 estava OK no passado, com prateleiras cheias de Sprite."
    
    # Gerar e guardar
    conteudo_md = generator.generate_markdown_report(mock_inspections, mock_alerts, mock_rag)
    generator.save_report(conteudo_md)
    print("\n[PRÉ-VISUALIZAÇÃO DO RELATÓRIO]\n")
    print(conteudo_md)