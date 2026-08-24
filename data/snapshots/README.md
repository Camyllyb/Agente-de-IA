# Snapshots de dados financeiros

Snapshots são **fotografias congeladas** de dados financeiros, usadas nos
experimentos científicos. Como valores de mercado mudam com o tempo, os mesmos
dados precisam ser fornecidos a **todas** as técnicas (zero-shot, few-shot,
chain-of-thought) e a **todos** os modelos avaliados. Assim, mudanças do mercado
não interferem na comparação entre técnicas.

## Organização

```
data/snapshots/
└── <conjunto>/            # ex.: "default"
    ├── PETR4.SA.json
    ├── VALE3.SA.json
    └── ...
```

O conjunto usado é definido por `SNAPSHOT_SET` (padrão: `default`).

## Formato de cada arquivo (`<SYMBOL>.json`)

```json
{
  "symbol": "PETR4.SA",
  "currency": "BRL",
  "as_of": "2024-07-01",
  "note": "...",
  "quote": {
    "price": 41.0,
    "date": "2024-07-01",
    "timestamp": "2024-07-01T21:00:00Z"
  },
  "history": [
    {"date": "2024-01-02", "open": 36.0, "high": 36.36, "low": 35.64, "close": 36.0, "volume": 1000000},
    ...
  ]
}
```

## ⚠️ Conjunto `default` = dados SINTÉTICOS

O conjunto `default` incluído no repositório é **fictício e determinístico**,
gerado por [`build_default_snapshots.py`](build_default_snapshots.py). Ele serve
apenas para os testes automatizados e para o **experimento offline de pipeline**.
**Não representa cotações reais de mercado** e não deve ser usado para conclusões
científicas.

Regenerar o conjunto sintético:

```bash
python data/snapshots/build_default_snapshots.py
```

## Gerando snapshots REAIS

Para experimentos com dados reais, congele dados da fonte ao vivo (yfinance) em
um novo conjunto (ex.: `2024h1`) e aponte `SNAPSHOT_SET` para ele. Utilize o
`LiveMarketDataProvider` para obter os dados e salve-os no mesmo formato acima.
Registre a data de captura (`as_of`) para rastreabilidade.
