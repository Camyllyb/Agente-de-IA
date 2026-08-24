# Pacote de reprodutibilidade — financial-prompt-agent

Gerado em: 2026-08-24T21:33:21.909099+00:00

Commit Git: `32ccdaa718aca84cd93e9d89b3a2d6bb2aca94d6`

## Conteúdo

- `protocol.json` — protocolo experimental congelado (decisões metodológicas).
- `dataset.json` — dataset de benchmark (30 questões).
- `snapshot_metadata.json` — metadados dos snapshots (checksums, período, fontes).
- `prompt_versions/` — prompts de sistema versionados de cada estratégia.
- `model_config.json` — configuração dos modelos (SEM chaves de API).
- `metric_definitions.json` — definição das métricas.
- `environment.txt` — versão do Python, SO, data, commit.
- `requirements_lock.txt` — versões exatas das bibliotecas.
- `manifest.json` — checksums e resumo.

## Como reproduzir

1. Recrie o ambiente: `pip install -r requirements_lock.txt`.
2. Configure as chaves de API por variáveis de ambiente (ver `.env.example`).
3. Restaure os snapshots congelados referenciados em `snapshot_metadata.json`.
4. Verifique a prontidão: `python -m experiments.readiness`.
5. Execute: `python -m experiments.runner --models-config --final --yes`.

**Este pacote NÃO contém chaves, segredos ou credenciais.**
