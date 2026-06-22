# BOT V11 PROFESSIONAL COMPLETO

## 🚀 O que é?

Bot de análise institucional que roda localmente no seu PC e manda relatórios para Telegram.

**Inclui:**
- ✅ Macro Real (FRED API)
- ✅ Técnica (SMC, ICT, Wyckoff, Volume, ML)
- ✅ Notícias (NewsAPI)

## 📦 Instalação

### 1. Deletar TUDO
```bash
Deleta todas as pastas e arquivos anteriores
```

### 2. Copiar os 10 arquivos para seu PC
```
bot_v11_completo.py
data_fetcher.py
macro_engine_v2.py
news_engine.py
smc_engine.py
ict_engine.py
wyckoff_engine.py
volume_liquidity_engine.py
ml_engine.py
requirements.txt
.env_template
```

### 3. Instalar dependências
```bash
pip install -r requirements.txt --break-system-packages
```

### 4. Configurar .env
```bash
Renomear: .env_template → .env

Editar e adicionar:
TELEGRAM_TOKEN=seu_token
TELEGRAM_CHAT=seu_chat_id
FRED_KEY=sua_chave_fred
NEWS_API_KEY=sua_chave_newsapi
```

### 5. Rodar o bot
```bash
python bot_v11_completo.py
```

## 📡 Comandos Telegram

- `/start` - Inicia
- `/help` - Menu
- `/eur` - Análise EURUSD
- `/jpy` - Análise USDJPY
- `/xau` - Análise OURO
- `/btc` - Análise BITCOIN
- `/summary` - Resumo dos 4 ativos

## 🔑 APIs Necessárias

### FRED (Dados Econômicos)
1. Ir em: https://fredaccount.stlouisfed.org/login
2. Criar conta
3. Pegar API key
4. Colar em `.env` (FRED_KEY)

### NewsAPI (Notícias)
1. Ir em: https://newsapi.org
2. Criar conta
3. Pegar API key
4. Colar em `.env` (NEWS_API_KEY)

### Telegram
1. Usar Token + Chat ID que já tem

## 📊 Estrutura

```
Macro (FRED)
    ↓
Notícias (NewsAPI)
    ↓
Análise Técnica (6 Engines)
    ↓
Relatório Telegram
```

## ⚙️ Engines Técnicos

1. **SMC** - Estrutura de mercado
2. **ICT** - Kill zones, Market bias
3. **Wyckoff** - Acumulação/Distribuição
4. **Volume** - Profile e liquidez
5. **ML** - Random Forest
6. **Macro** - FRED + Análise econômica

## 🔧 Troubleshooting

**Erro 409 Telegram:**
- Certifique que só um bot tá rodando
- Aperta Ctrl+C
- Roda de novo

**Sem dados:**
- Verifica conexão internet
- Confere as APIs

**Python 3.13 error:**
- Use: `pip install --break-system-packages`

## 📝 Notas

- Bot roda 24/7 enquanto PC tá ligado
- Puxas dados REAIS do mercado
- Análise MACRO + TÉCNICA + NOTÍCIAS
- Sem erros, código otimizado

---

**Versão:** V11 Professional
**Data:** Junho 2026
