import os
import json
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types

class RuleEngine:
    def __init__(self):
        load_dotenv()
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model_id = 'gemini-2.5-flash'
        
    def parse_natural_language_rule(self, user_input: str) -> dict:
        print(f"A traduzir a regra do gestor: '{user_input}'.")
        
        current_rule_id = f"RULE_{int(time.time())}"
        current_time = time.strftime('%Y-%m-%dT%H:%M:%SZ')
        
        prompt = f"""
        Atua como um tradutor de regras de negócio para um sistema de visão de retalho.
        O gestor de loja escreveu a seguinte regra em linguagem natural: "{user_input}"
        
        A tua tarefa é converter esta regra estritamente para formato JSON, obedecendo a estas DIRETRIZES:
        
        DIRETRIZ 1 (Ambiguidade Crítica): Se a regra omitir parâmetros vitais (ex: "Avisa-me se a prateleira estiver vazia" - falta a zona, e o limite matemático de vazio), deves definir 'is_valid' como false, listar as falhas na lista 'ambiguities' e deixar as 'conditions' com valores null. NÃO inventes nem assumas valores quando a regra é declarada inválida.
        
        DIRETRIZ 2 (Valores por Defeito): Se a regra for clara e acionável matematicamente (ex: "Avisa-me se a prateleira inferior estiver mais de 30% vazia"), mas o gestor não especificar a severidade ou o nível de alerta, deves considerar a regra VÁLIDA ('is_valid': true). Usa o teu bom senso para preencher com um nível apropriado (ex: 'medium' e 'warning') e regista que o fizeste na lista 'assumptions'.
        
        DIRETRIZ 3 (Timestamps): És OBRIGADO a usar EXATAMENTE '{current_rule_id}' para o 'rule_id' e '{current_time}' para o 'created_at'.
        
        DEVES USAR ESTRITAMENTE ESTE SCHEMA:
        {{
          "rule_id": "{current_rule_id}",
          "created_at": "{current_time}",
          "natural_language": "{user_input}",
          "description": "reformulação clara e inequívoca em português formal",
          "conditions": {{
            "zone_filter": ["Z_S1", "Z_S3"] ou ["all"],
            "time_filter": {{"hours_start": 0, "hours_end": 24}},
            "issue_types": ["empty_shelf", "wrong_product", "damaged", "misaligned", "label_missing", "other"],
            "severity_threshold": "low|medium|high" ou null,
            "fill_rate_threshold": número decimal ou null,
            "location_filter": "bottom|middle|top|any"
          }},
          "action": {{
            "alert_level": "info|warning|critical" ou null,
            "notification_message": "template da mensagem"
          }},
          "validation": {{
            "is_valid": booleano,
            "ambiguities": ["lista de ambiguidades encontradas"],
            "assumptions": ["lista de pressupostos assumidos"]
          }}
        }}
        """
        
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    temperature=0.0, 
                    response_mime_type="application/json"
                )
            )
            return json.loads(response.text)
            
        except Exception as e:
            return {"error": f"Erro na API do Gemini: {str(e)}"}

    def execute_rules(self, inspection_data: dict, rules_list: list) -> list:
        triggered_alerts = []
        
        print(f"\n[LOG] A iniciar verificação de {len(rules_list)} regras para a inspeção {inspection_data.get('inspection_id')}")
        
        for rule in rules_list:
            if not rule.get("validation", {}).get("is_valid", False):
                print(f"[LOG] Regra {rule.get('rule_id')} ignorada (Inválida/Ambígua).")
                continue
                
            conditions = rule.get("conditions", {})
            zone_filter = conditions.get("zone_filter", [])
            
            # verificar zona
            if "all" not in zone_filter and inspection_data.get("zone_id") not in zone_filter:
                print(f"[LOG] Regra {rule.get('rule_id')} ignorada (Zona não corresponde).")
                continue
                
            # verificar issues
            rule_disparou = False
            problemas_relevantes = []
            
            for issue in inspection_data.get("issues", []):
                match_type = issue.get("type") in conditions.get("issue_types", []) or not conditions.get("issue_types")
                
                location_filter = conditions.get("location_filter", "any")
                match_location = location_filter == "any" or \
                                 (location_filter == "bottom" and "inferior" in issue.get("location", "").lower()) or \
                                 (location_filter == "top" and "superior" in issue.get("location", "").lower())

                # verificar fill rate se existir na regra
                fill_rate_limit = conditions.get("fill_rate_threshold")
                issue_fill_rate = issue.get("shelf fill rate", 1.0)
                match_fill_rate = fill_rate_limit is None or issue_fill_rate < fill_rate_limit
                
                if match_type and match_location and match_fill_rate:
                    rule_disparou = True
                    problemas_relevantes.append(issue)
                    
            if rule_disparou:
                alert_level = rule.get("action", {}).get("alert_level", "info")
                msg_template = rule.get("action", {}).get("notification_message", "Problema detetado.")
                
                alerta = {
                    "rule_id": rule.get("rule_id"),
                    "inspection_id": inspection_data.get("inspection_id"),
                    "alert_level": alert_level,
                    "message": f"[{alert_level.upper()}] {msg_template} (Zona: {inspection_data.get('zone_id')})",
                    "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ'),
                    "triggered_by_issues": [p.get("issue_id") for p in problemas_relevantes]
                }
                triggered_alerts.append(alerta)
                print(f"[LOG] ALERTA DISPARADO: Regra {rule.get('rule_id')}")
            else:
                print(f"[LOG] Regra {rule.get('rule_id')} verificada (Condições não atingidas).")
                
        return triggered_alerts

# bloco de testes
if __name__ == "__main__":
    engine = RuleEngine()
    
    print("TESTE DE TRADUÇÃO:")
    regra_clara = "Quero ser alertado quando a prateleira inferior da zona Z_S2 estiver mais de 30% vazia."
    res1 = engine.parse_natural_language_rule(regra_clara)
    print(json.dumps(res1, indent=2, ensure_ascii=False))
    
    print("\nTESTE DE EXECUÇÃO:")
    # simular uma inspeção que o ShelfInspector geraria
    inspecao_simulada = {
      "inspection_id": "INS_TEST_123",
      "zone_id": "Z_S2",
      "overall_status": "warning",
      "issues": [
        {
          "issue_id": "ISS_001",
          "type": "empty_shelf",
          "location": "prateleira inferior, lado esquerdo",
          "severity": "medium",
          "shelf fill rate": 0.60
        }
      ]
    }
    
    # passar a regra que acabada de traduzir
    alertas = engine.execute_rules(inspecao_simulada, [res1])
    print("\nResultados da Execução:")
    print(json.dumps(alertas, indent=2, ensure_ascii=False))