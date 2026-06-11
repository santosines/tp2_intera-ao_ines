# Retail Vision Intelligence System

Este projeto implementa um sistema de inspeção automatizada de prateleiras utilizando modelos de linguagem multimodais (LMMs). O sistema permite a deteção de anomalias (ruturas, desalinhamentos), gestão de regras de negócio em linguagem natural e uma base de conhecimento histórica (RAG).

## Estrutura do Projeto
- `data/`: Contém as imagens (dataset) e os relatórios gerados.
- `src/`: Código fonte dos componentes principais (`shelf_inspector.py`, `rule_engine.py`, etc.).
- `rules/`: Regras de negócio persistidas em formato JSON.
- `vectorstore/`: Base de dados ChromaDB (gerada em runtime).
- `cache/`: Cache local de resultados da API para otimização de quota.

## Configuração
1. **Ambiente:** Cria um ficheiro `.env` na raiz do projeto seguindo o modelo `.env.example`.
2. **API Key:** Define a tua `GEMINI_API_KEY` no ficheiro `.env`. 
3. **Dependências:** Instala os requisitos:
   ```bash
   pip install -r requirements.txt

## Como Executar
1. **Interface Conversacional**
python interface.py
2. **Harness de Avaliação**
python evaluate.py --images-dir test_images/ --output evaluation_report.json

## Decisões de Design
- O sistema utiliza Gemini 2.5 Flash via API para evitar dependências de GPU local.  
- Foi implementado cache local via hash MD5 para respeitar os limites de quota da API e garantir reprodutibilidade.  
- As regras são validadas por um módulo de RuleEngine que deteta ambiguidades antes da execução. 