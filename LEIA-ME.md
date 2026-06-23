# BOT V11 — Trader Macro Profissional

## O que é
Bot Telegram que analisa 4 ativos com dados reais do mercado:
- 🥇 XAUUSD (Ouro)
- 💶 EURUSD
- 💴 USDJPY
- ₿ BTCUSD

## Passo a passo para rodar

### 1. Instalar dependências
Abra o PowerShell na pasta do bot e rode:
```
pip install -r requirements.txt
```

### 2. Criar o arquivo .env
Crie um arquivo chamado `.env` na pasta com esse conteúdo:
```
TELEGRAM_TOKEN=seu_token_do_telegram
TELEGRAM_CHAT=seu_chat_id
FRED_KEY=sua_chave_fred
```

### 3. Rodar o bot
```
python bot_v11.py
```

### 4. Comandos no Telegram
- `/start` — menu de comandos
- `/macro` — contexto macro global
- `/analise` — resumo dos 4 ativos
- `/xau` — análise Ouro
- `/eur` — análise EUR/USD
- `/jpy` — análise USD/JPY
- `/btc` — análise Bitcoin

### 5. Análise automática
O bot envia análise automaticamente:
- 08:00 UTC — Abertura de Londres
- 13:00 UTC — Abertura de NY

## Arquivos do projeto
```
bot_v11/
├── bot_v11.py           ← Bot principal (rodar este)
├── data_fetcher.py      ← Puxa dados do mercado (YFinance)
├── macro_engine.py      ← Dados macro via FRED API
├── technical_engine.py  ← SMC, Wyckoff, S/R, FVG
├── confluence_engine.py ← Score e recomendação final
├── requirements.txt     ← Dependências
└── .env                 ← Suas chaves (criar manualmente)
```

## Onde pegar a FRED API key (gratuito)
1. Acesse: https://fred.stlouisfed.org/docs/api/api_key.html
2. Crie uma conta gratuita
3. Copie a chave e cole no .env
