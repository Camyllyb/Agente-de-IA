# Relatório de validação — financial-prompt-agent

Data da validação: 2026-08-24 · Python 3.11.9 · LangChain 1.3.16 · LangGraph 1.2.11 ·
FastAPI 0.141.1 · Streamlit 1.x · pytest 9.1.1.

## 1. Implementado (funcionalidades realmente existentes)

- **Configuração central** (`app/config`): settings via variáveis de ambiente,
  logging centralizado, `models.yaml`, `pricing.yaml`.
- **Camada de LLM** (`app/services/llm`): abstração `LLMProvider`; provedores
  OpenAI, Anthropic, Google, OpenRouter (import *lazy*) + `FakeLLMProvider`;
  fábrica `create_llm_provider`; erros tipados.
- **Ferramentas financeiras** (`app/tools`): `MarketDataProvider` com
  `LiveMarketDataProvider` (yfinance) e `SnapshotMarketDataProvider`; ferramentas
  `get_stock_quote`, `get_stock_history`, `compare_stocks`, `calculate_return`
  (dados estruturados; nunca inventam valores; declaram "não encontrado").
- **Estratégias de prompting** (`app/prompts`): `PromptStrategy` + Zero-shot,
  Few-shot, Chain-of-thought; mesma tarefa/contexto/dados/restrições/formato,
  variando só a técnica; `prompt_version` versionado; `get_prompt_strategy`.
- **Agente** (`app/agents`): `FinancialAgent` sobre `create_agent` (API atual do
  LangChain); recebe modelo × estratégia × fonte de dados; registra ferramentas,
  tokens e latência.
- **API** (`app/api`): `POST /api/chat`, `GET /api/models`, `GET /api/strategies`,
  `GET /health`; tratamento de erros sem stack traces.
- **Interface** (`frontend`): página de chat (config + métricas de execução) e
  página Experimentos (painel com filtros e gráficos).
- **Experimentos** (`experiments`): dataset `questions.json` (20 questões, 5
  categorias); `ExperimentRunner` (modelos × técnicas × questões × repetições);
  `--dry-run`, `--max-runs`, guarda `--yes`; SQLite + exportação CSV; oráculo
  determinístico para validar o pipeline; `preflight`, `analysis`, `exporter`,
  `statistics`, `report`.
- **Métricas** (`app/metrics`): precisão factual, latência, tokens, custo
  (tabela versionada; `null` se não configurada), taxa de sucesso, *tool
  accuracy*, avaliação humana cega (rubrica 1–5) e LLM-as-a-judge (opcional,
  identificado como IA).

## 2. Testes automatizados

**90 testes, 90 aprovados, 0 falhas** (offline; sem internet/chave/crédito).

| Arquivo | Cobertura |
|---|---|
| test_health | endpoint /health |
| test_llm_providers | fábrica, config inválida, provider não suportado, fake |
| test_financial_tools | snapshot, não-encontrado, retorno, comparação, tools LangChain |
| test_prompt_strategies | invariância experimental, versionamento |
| test_agent | laço agente→ferramenta→dados→resposta (FakeLLM) |
| test_api | chat, models, strategies, erros sem stack trace |
| test_experiments | plano, dry-run, persistência, falha registrada, CSV |
| test_metrics | factual, custo, tool accuracy, avaliação cega, LLM-judge |
| test_analysis | agregação do painel |
| test_frontend | execução das páginas Streamlit (AppTest) |
| test_statistics | descritiva, Friedman, Wilcoxon+Holm |
| test_preflight | dataset/snapshots/referências e halt sem chaves |

## 3. Verificações de execução (reais)

- **Importação**: 57 módulos importam sem erro.
- **Backend**: `uvicorn` sobe; `/health`, `/api/strategies` e `POST /api/chat`
  (fake) respondem corretamente.
- **Interface**: Streamlit sobe (`/_stcore/health` = ok, root 200); ambas as
  páginas executam sem exceção (AppTest).
- **Segurança**: nenhuma chave de API hardcoded no código; `.env` no `.gitignore`.
- **Pipeline offline**: 60 execuções (oráculo × 3 técnicas × 20 questões), 0
  falhas; artefatos exportados (raw/aggregated/blind/metadata) em
  `experiments/results/pipeline_validation/`. **Estes números são validação de
  pipeline com um mock determinístico — NÃO representam desempenho de LLM real.**

## 4. Problemas encontrados e correções

- `matplotlib` 3.11 removeu `boxplot(labels=...)` → corrigido para `tick_labels`.
- Aviso remanescente (não bloqueante): `StarletteDeprecationWarning` sobre `httpx`
  no `TestClient` — não afeta os testes.

## 5. Execução real com LLM (o que configurar)

1. Copie `.env.example` → `.env` e preencha as chaves dos provedores desejados:
   `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `OPENROUTER_API_KEY`.
2. Adicione os modelos em `app/config/models.yaml` (não fixe versões obsoletas).
3. (Opcional) Preencha `app/config/pricing.yaml` para estimar custo.
4. Verifique o pré-voo: `python -m experiments.preflight`.
5. Execute: `python -m experiments.runner --models-config --repetitions 5 --yes`.

**Estado atual do ambiente:** nenhum provedor real tem chave configurada
(apenas `fake`). Portanto **nenhuma chamada externa a LLM foi realizada** e
nenhum resultado científico foi produzido. Isto é declarado explicitamente — não
foram gerados números fictícios.
