import os
import json
import shlex
from pathlib import Path

from shelf_inspector import ShelfInspector
from rule_engine import RuleEngine
from rag_memory import RagMemory
from report_generator import ReportGenerator

class RetailInterface:
    def __init__(self):
        print("A iniciar Retail Vision Intelligence System.")
        self.inspector = ShelfInspector()
        self.engine = RuleEngine()
        self.memory = RagMemory()
        self.reporter = ReportGenerator()
        
        # configurar o estado da sessão (memória a curto prazo)
        self.session_inspections = []
        self.session_alerts = []
        self.rules = []
        
        # configurar persistência de regras
        self.rules_dir = Path("rules")
        self.rules_dir.mkdir(parents=True, exist_ok=True)
        self.load_rules()
        
        print("\nDigite 'help' para ver os comandos ou 'exit' para sair.")

    def load_rules(self):
        #carrega as regras guardadas em ficheiros JSON na pasta rules
        for rule_file in self.rules_dir.glob("*.json"):
            try:
                with open(rule_file, 'r', encoding='utf-8') as f:
                    self.rules.append(json.load(f))
            except Exception:
                pass
        print(f"[{len(self.rules)} regras carregadas na memória]")

    def save_rule(self, rule_data):
        #guarda uma nova regra em disco
        file_path = self.rules_dir / f"{rule_data['rule_id']}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(rule_data, f, indent=2, ensure_ascii=False)
        self.rules.append(rule_data)

    def execute_command(self, user_input):
        #processa o comando do utilizador, try-except previne stack traces
        try:
            # vividir o comando respeitando aspas
            parts = shlex.split(user_input)
            if not parts:
                return

            cmd = parts[0].lower()

            if cmd in ['exit', 'quit']:
                print("A encerrar o sistema.")
                return False

            elif cmd == 'help':
                self.show_help()

            elif cmd == 'inspect':
                self.cmd_inspect(parts)

            elif cmd == 'add' and len(parts) >= 3 and parts[1].lower() == 'rule':
                self.cmd_add_rule(parts[2])

            elif cmd == 'list' and len(parts) >= 2 and parts[1].lower() == 'rules':
                self.cmd_list_rules()

            elif cmd == 'history' and len(parts) >= 2:
                self.cmd_history(parts[1])

            elif cmd == 'report':
                self.cmd_report()

            else:
                print(f"Comando não reconhecido: '{parts[0]}'. Digite 'help' para ajuda.")

        except Exception as e:
            #nunca mostrar stack traces!
            print(f"\n[ERRO DE SISTEMA] Ocorreu um problema ao processar o comando.")
            print(f"Detalhe: {str(e)}")
            print("Por favor, verifique a sintaxe e tente novamente.\n")
        
        return True

    #COMANDOS ESPECÍFICOS

    def cmd_inspect(self, parts):
        #exemplo: inspect Z_S2 --image data/images/normal_test/exemplo1.jpg
        if len(parts) < 4 or parts[2] != '--image':
            print("Uso correto: inspect <zona> --image <caminho_da_imagem>")
            return
            
        zone_id = parts[1]
        image_path = parts[3]
        
        if not os.path.exists(image_path):
            print(f"Erro: A imagem '{image_path}' não foi encontrada.")
            return
            
        print(f"\nA inspecionar a imagem {image_path} na zona {zone_id}.")
        
        # analisar imagem
        resultado = self.inspector.inspect_image(image_path, zone_id, strategy="strategy_c_fewshot")
        if "error" in resultado:
            print(resultado["error"])
            return
            
        self.session_inspections.append(resultado)
        print(f"- Inspeção concluída. Status: {resultado.get('overall_status').upper()}")
        
        # guardar no RAG logo
        self.memory.index_inspection(resultado)
        
        # verificar regras
        if self.rules:
            alertas = self.engine.execute_rules(resultado, self.rules)
            if alertas:
                for a in alertas:
                    print(f"   . {a['message']}")
                self.session_alerts.extend(alertas)

    def cmd_add_rule(self, rule_text):
        #exemplo: add rule "Avisa-me se a prateleira da zona Z_S2 estiver vazia" 
        print("\nA traduzir regra.")
        parsed_rule = self.engine.parse_natural_language_rule(rule_text)
        
        # tratar ambiguidades interativamente 
        validation = parsed_rule.get("validation", {})
        if not validation.get("is_valid", False) and validation.get("ambiguities"):
            print("\nA sua regra é ambígua. O sistema não pode assumir parâmetros vitais.")
            print("Ambiguidades detetadas:")
            for amb in validation.get("ambiguities", []):
                print(f" - {amb}")
            print("Por favor, reescreva a regra de forma mais clara.")
            return

        self.save_rule(parsed_rule)
        print(f"Regra '{parsed_rule['rule_id']}' adicionada e ativada com sucesso.")
        print(f"Interpretação do sistema: {parsed_rule['description']}")

    def cmd_list_rules(self):
        print("\nRegras ativas:")
        if not self.rules:
            print("Nenhuma regra ativa no momento.")
        for r in self.rules:
            print(f"[{r['rule_id']}] {r['description']}")

    def cmd_history(self, question):
        #exemplo: history "qual o estado da Sprite na Z_S2?"
        resposta = self.memory.query_memory(question)
        print("\n[RAG] Resposta:")
        print(resposta)

    def cmd_report(self):
        if not self.session_inspections:
            print("Não há inspeções nesta sessão para gerar um relatório.")
            return
            
        print("\nA gerar o relatório final com o LLM.")
        
        # pede ao RAG um contexto geral das zonas inspecionadas para incluir no relatório
        zonas_unicas = list(set([i.get("zone_id") for i in self.session_inspections]))
        pergunta_rag = f"Faz um resumo histórico simples dos problemas encontrados anteriormente nestas zonas: {', '.join(zonas_unicas)}"
        contexto_rag = self.memory.query_memory(pergunta_rag)
        
        md_content = self.reporter.generate_markdown_report(self.session_inspections, self.session_alerts, contexto_rag)
        self.reporter.save_report(md_content)

    def show_help(self):
        print("\nComandos Disponíveis:")
        print("  inspect <ZONA> --image <CAMINHO>   : Inspeciona uma imagem.")
        print("  add rule \"<TEXTO DA REGRA>\"        : Adiciona uma regra em linguagem natural.")
        print("  list rules                         : Mostra as regras ativas.")
        print("  history \"<PERGUNTA>\"               : Faz uma pergunta ao histórico (RAG).")
        print("  report                             : Gera o relatório Markdown da sessão atual.")
        print("  exit                               : Encerra o sistema.")
        
# loop principal
if __name__ == "__main__":
    app = RetailInterface()
    running = True
    while running:
        try:
            comando = input("Retail-AI > ")
            if comando.strip():
                running = app.execute_command(comando)
        except KeyboardInterrupt:
            print("\nA encerrar o sistema abruptamente.")
            break