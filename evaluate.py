import os
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from shelf_inspector import ShelfInspector

class Evaluator:
    def __init__(self):
        load_dotenv()
        self.inspector = ShelfInspector()
        self.judge_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.judge_model = 'gemini-2.5-flash'

    def llm_as_judge_hallucination(self, image_path: str, model_reasoning: str, issues: list) -> bool:
        if not issues:
            return False 
            
        print(f"      [LLM-as-Judge] A avaliar alucinação para {Path(image_path).name}.")
        prompt = f"""
        Atua como um juiz imparcial. Tens de avaliar se a análise de uma imagem de retalho contém alucinações.
        
        Raciocínio gerado: {model_reasoning}
        Problemas reportados: {json.dumps(issues, ensure_ascii=False)}
        
        Avalia a imagem fornecida cruzando-a com estes dados. Existe alguma afirmação nos problemas reportados que seja CLARAMENTE INVENTADA ou não verificável na imagem?
        Responde APENAS com um JSON simples: {{"is_hallucination": true/false}}
        """
        try:
            image_file = self.judge_client.files.upload(file=image_path)
            response = self.judge_client.models.generate_content(
                model=self.judge_model,
                contents=[image_file, prompt],
                config=types.GenerateContentConfig(temperature=0.0, response_mime_type="application/json")
            )
            result = json.loads(response.text)
            return result.get("is_hallucination", False)
        except Exception:
            return False 

    def run_evaluation(self, images_dir: str, output_file: str, ground_truth_path: str, strategy: str):
        print(f"\n[INÍCIO DA AVALIAÇÃO] Estratégia: {strategy}")
        img_paths = list(Path(images_dir).glob("*.jpg")) + list(Path(images_dir).glob("*.jpeg"))
        
        if not img_paths:
            print("Erro: Nenhuma imagem encontrada no path.")
            return

        # carregar ground truth
        gt_data = {}
        if ground_truth_path and os.path.exists(ground_truth_path):
            with open(ground_truth_path, 'r', encoding='utf-8') as f:
                gt_data = json.load(f)
            print(f"[LOG] Ground Truth carregado ({len(gt_data)} imagens anotadas).")

        metrics = {
            "strategy_used": strategy,
            "total_images_processed": len(img_paths),
            "json_parse_rate_pct": 0.0,
            "hallucination_rate_pct": 0.0,
            "issue_detection_rate_pct": 0.0,
            "false_positive_rate_pct": 0.0,
            "severity_accuracy_pct": 0.0,
            "raw_results": []
        }

      
        successful_parses = 0
        hallucinated_cases = 0
        total_tp, total_fp, total_fn = 0, 0, 0
        total_correct_severity = 0

        for img_path in img_paths:
            img_str = str(img_path)
            print(f"\nA avaliar: {img_path.name}")
            
            # passar a estratégia de forma dinâmica
            result = self.inspector.inspect_image(img_str, zone_id="EVAL_ZONE", strategy=strategy)
            
            is_valid_json = "error" not in result
            is_hallucinated = False
            
            if is_valid_json:
                successful_parses += 1
                pred_issues = result.get("issues", [])
                
                is_hallucinated = self.llm_as_judge_hallucination(img_str, result.get("model_reasoning", ""), pred_issues)
                if is_hallucinated: hallucinated_cases += 1

                # cruzr com ground truth
                if gt_data and img_path.name in gt_data:
                    gt_issues = gt_data[img_path.name]
                    gt_types = [i.get("type") for i in gt_issues]
                    
                    tp_local = 0
                    for p_issue in pred_issues:
                        p_type = p_issue.get("type")
                        if p_type in gt_types:
                            tp_local += 1
                            total_tp += 1
                            for g_issue in gt_issues:
                                if g_issue.get("type") == p_type and g_issue.get("severity") == p_issue.get("severity"):
                                    total_correct_severity += 1
                                    break
                            gt_types.remove(p_type) 
                        else:
                            total_fp += 1
                    
                    total_fn += len(gt_types) 

            else:        
                print(f"      [ERRO] Falha no parse JSON: {result.get('error')}")

            metrics["raw_results"].append({
                "image": img_path.name,
                "parsed_successfully": is_valid_json,
                "hallucination_detected": is_hallucinated,
                "system_output": result
            })

        # caalculo final metricas
        metrics["json_parse_rate_pct"] = (successful_parses / len(img_paths)) * 100
        if successful_parses > 0:
            metrics["hallucination_rate_pct"] = (hallucinated_cases / successful_parses) * 100

        if gt_data:
            # Issue Detection Rate (Recall) = TP / (TP + FN)
            if (total_tp + total_fn) > 0:
                metrics["issue_detection_rate_pct"] = round((total_tp / (total_tp + total_fn)) * 100, 2)
            else:
                metrics["issue_detection_rate_pct"] = 100.0 # se não havia problemas e não detetou, 100% de recall
            
            # False Positive Rate = FP / Total Predições
            total_pred = total_tp + total_fp
            if total_pred > 0:
                metrics["false_positive_rate_pct"] = round((total_fp / total_pred) * 100, 2)
                
            # Severity Accuracy = Correct Severity / TP
            if total_tp > 0:
                metrics["severity_accuracy_pct"] = round((total_correct_severity / total_tp) * 100, 2)
        else:
            metrics["issue_detection_rate_pct"] = "Ground Truth não fornecido"
            metrics["false_positive_rate_pct"] = "Ground Truth não fornecido"
            metrics["severity_accuracy_pct"] = "Ground Truth não fornecido"

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, indent=4, ensure_ascii=False)

        print(" AVALIAÇÃO CONCLUÍDA ")
        print(f" Estratégia Usada    : {strategy}")
        print(f" Imagens processadas : {metrics['total_images_processed']}")
        print(f" JSON Parse Rate     : {metrics['json_parse_rate_pct']:.1f}%")
        print(f" Hallucination Rate  : {metrics['hallucination_rate_pct']:.1f}%")
        if gt_data:
            print(f" Issue Detection Rate: {metrics['issue_detection_rate_pct']}%")
            print(f" False Positive Rate : {metrics['false_positive_rate_pct']}%")
            print(f" Severity Accuracy   : {metrics['severity_accuracy_pct']}%")
        print(f"\n Relatório completo: {output_file}")

# interface cli
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retail Vision System - Evaluation Harness")
    
    parser.add_argument("--images-dir", default="test_images/", help="Diretório com as imagens de teste")
    parser.add_argument("--output", default="evaluation_report.json", help="Caminho para guardar o relatório JSON")
    parser.add_argument("--ground-truth", required=False, default=None, help="Ficheiro opcional de ground truth")
    parser.add_argument("--strategy", required=False, default="strategy_a_zeroshot", help="Estratégia de prompt")
    
    args = parser.parse_args()
    
    evaluator = Evaluator()
    evaluator.run_evaluation(args.images_dir, args.output, args.ground_truth, args.strategy)