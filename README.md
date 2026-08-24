# financial-prompt-agent

**Laboratório experimental de Engenharia de Prompt aplicada a agentes financeiros.**

Software de pesquisa acadêmica sobre **Engenharia de Prompt em Large Language
Models**. Compara três estratégias de prompting — **zero-shot**, **few-shot** e
**chain-of-thought / raciocínio estruturado** — aplicadas aos **mesmos** problemas
financeiros, em **diferentes** modelos, sob **métricas objetivas**. O mesmo
sistema funciona como um **agente financeiro real**, que consulta dados por meio
de ferramentas.

> ⚠️ **Princípios metodológicos**
> - O software **não** assume previamente que uma técnica é melhor; deixa os
>   resultados mostrarem, segundo métricas objetivas.
> - **Resultados experimentais nunca são fabricados.**
> - Cotações e valores de mercado vêm **sempre** de ferramentas — nunca inventados
>   pelo modelo. Sem dado disponível, o sistema declara a limitação.
> - As respostas **não** constituem recomendação de investimento.

---

## Requisitos

- Python **3.11+**
- Dependências: [`requirements.txt`](requirements.txt)
- Chaves de API dos provedores (opcionais; só para execução real) — via variáveis
  de ambiente. **Nunca** coloque chaves no código.

Nenhum modelo é obrigatório. Provedores suportados: **OpenAI, Anthropic, Google,
OpenRouter** e um provedor **fake** (determinístico, offline) para desenvolvimento
e testes.

---

## Instalação

```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1   |   Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env
```

Provedores de LLM, a fonte ao vivo (`yfinance`) e as libs de análise
(`scipy`, `matplotlib`) são **opcionais** — veja os comentários no
[`requirements.txt`](requirements.txt).

### Variáveis de ambiente (execução real)

Configure no `.env` **apenas** os provedores que for usar:

| Variável | Uso |
|---|---|
| `OPENAI_API_KEY` | provedor `openai` |
| `ANTHROPIC_API_KEY` | provedor `anthropic` |
| `GOOGLE_API_KEY` | provedor `google` |
| `OPENROUTER_API_KEY` | provedor `openrouter` |

Os identificadores de modelo ficam em [`app/config/models.yaml`](app/config/models.yaml)
(ou na requisição). **Não** fixe versões de modelos que possam ficar obsoletas.

---

## Como executar

### API (FastAPI)

```bash
python main.py                      # http://localhost:8000
uvicorn app.api.app:app --reload    # alternativa
curl http://localhost:8000/health
```

Endpoints: `GET /health`, `POST /api/chat`, `GET /api/models`, `GET /api/strategies`.
Documentação interativa em `/docs`.

### Interface (Streamlit)

```bash
streamlit run frontend/streamlit_app.py
```

Página **principal** (chat com configuração de modelo/provider/técnica/fonte e
métricas de execução) e página **Experimentos** (painel de resultados).

### Experimentos científicos

```bash
# Pré-voo: verifica chaves, dataset, snapshots e referências; estima chamadas/custo
python -m experiments.preflight

# Pré-visualização do plano (nenhuma chamada é feita)
python -m experiments.runner --dry-run

# Pipeline OFFLINE (oráculo determinístico — NÃO é um LLM real)
python -m experiments.runner --oracle --export experiments/results/pipeline_raw.csv

# Execução REAL (exige --yes e chaves configuradas)
python -m experiments.runner --provider openai --model <modelo> --repetitions 5 --yes
```

O runner registra tudo em SQLite (`data/experiments.db`) e exporta CSV. Falhas
são registradas e a execução continua — **nunca** são substituídas por valores
inventados. Guardas explícitas (`--dry-run`, `--max-runs`, `--yes`) evitam
chamadas pagas acidentais.

### Testes

```bash
pytest
```

Os testes **não** dependem de internet, de chaves de API ou de créditos pagos.

---

## Arquitetura

```
financial-prompt-agent/
├── app/
│   ├── api/            # FastAPI: app factory, rotas, tradução de erros
│   ├── agents/         # FinancialAgent (LangChain create_agent)
│   ├── config/         # settings, logging, models.yaml, pricing.yaml
│   ├── models/         # schemas Pydantic (LLM, mercado, chat, agente)
│   ├── prompts/        # PromptStrategy: zero/few/chain-of-thought + registro
│   ├── services/       # camada de LLM (providers + fábrica + fake) e agent_service
│   ├── tools/          # ferramentas financeiras + MarketDataProvider (live/snapshot)
│   └── metrics/        # precisão factual, custo, tool accuracy, humana, LLM-judge
├── experiments/
│   ├── datasets/       # questions.json + gerador
│   ├── runner/         # ExperimentRunner, storage (SQLite/CSV), CLI, oráculo
│   ├── evaluators/     # (reservado)
│   ├── results/        # saídas (CSV/JSON) — geradas
│   ├── analysis.py     # agregação para o painel/artigo
│   ├── exporter.py     # raw/aggregated/blind/metadata
│   ├── preflight.py    # verificação pré-experimento
│   └── statistics.py   # estatística descritiva + testes
├── data/snapshots/     # dados financeiros congelados (reprodutibilidade)
├── frontend/           # interface Streamlit (chat + Experimentos)
├── tests/              # testes automatizados (offline)
└── main.py
```

### Desacoplamento (essencial para os experimentos)

- **Trocar o modelo sem alterar o agente**: abstração `LLMProvider` +
  `create_llm_provider(config)`. A biblioteca de cada provedor é importada de
  forma *lazy* (só quando usada).
- **Trocar a fonte financeira sem alterar o agente**: abstração
  `MarketDataProvider` (`LiveMarketDataProvider` ↔ `SnapshotMarketDataProvider`).
- **Trocar a técnica de prompting sem alterar o resto**: abstração
  `PromptStrategy` + `get_prompt_strategy(name)`. As três estratégias compartilham
  a mesma tarefa/contexto/dados/restrições/formato; só a técnica varia.
- O agente recebe `model` × `prompt_strategy` × `market_data_provider`, permitindo
  a **mesma** pergunta com técnicas/modelos diferentes.

---

## Métricas

**Automáticas:** precisão factual (numérica com tolerância; categórica por termos),
latência (ms), tokens (in/out/total), custo (tabela versionada — `null` se não
configurada), taxa de sucesso, *tool accuracy*.

**Humana (cega):** CSV anonimizado e randomizado (o avaliador não sabe modelo nem
técnica), notas 1–5 (clareza, relevância, completude, precisão percebida) com
rubrica objetiva; reimportação via mapeamento separado.

**LLM-as-a-judge (opcional):** sempre identificado como IA (`evaluator = llm_judge:…`)
e **nunca** misturado à avaliação humana.

---

## Dados sintéticos vs. reais

O conjunto de snapshots `default` e o `questions.json` incluídos são **sintéticos**
(determinísticos), destinados **apenas** a testes de pipeline. **Não** representam
dados reais de mercado. Para pesquisa real, gere snapshots a partir da fonte ao
vivo e recompute as referências (ver [`data/snapshots/README.md`](data/snapshots/README.md)).

---

## Segurança

- Chaves de API carregadas **apenas** do ambiente; `.env` está no `.gitignore`.
- Nenhuma chave é exibida na API ou na interface.
- A API não envia stack traces ao cliente (erros viram respostas estruturadas).

---

## Uso acadêmico

Software para pesquisa em Engenharia de Prompt. Não constitui recomendação de
investimento.
