# SmartKrishi - AI Smart Farming Advisor
> Powered by IBM watsonx.ai Granite Models + RAG Pipeline

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-green.svg)](https://flask.palletsprojects.com)
[![IBM watsonx](https://img.shields.io/badge/IBM-watsonx.ai-blue.svg)](https://www.ibm.com/products/watsonx-ai)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🌾 What is SmartKrishi?

SmartKrishi is an AI-powered smart farming advisor built for Indian farmers. It combines **IBM Granite AI** with **Retrieval-Augmented Generation (RAG)** to provide accurate, context-aware advice on:

- 🐛 **Pest & Disease Diagnosis** — Photo description + symptom-based AI diagnosis
- 🌱 **Crop Recommendations** — Region, season & soil-based suggestions
- 🌧️ **Weather Advisory** — Real-time forecasts with farming guidance
- 📊 **Live Mandi Prices** — Real-time agmarknet market prices
- 🧪 **Soil Analysis** — Interpret soil test reports + fertilizer schedules
- 🏛️ **Government Schemes** — PM-KISAN, PMFBY, KCC, and 50+ more
- 🗣️ **11 Indian Languages** — Hindi, Tamil, Telugu, Kannada, Bengali, Marathi, Gujarati, Punjabi, Malayalam, Odia, Urdu
- 🎤 **Voice Input/Output** — Web Speech API for voice interaction

---

## 🏗️ Architecture

```
SmartKrishi/
├── app/
│   ├── __init__.py                 # Flask application factory
│   ├── agent_instructions.py       # 🔧 CUSTOMIZE AI BEHAVIOR HERE
│   ├── models/
│   │   └── database.py             # SQLAlchemy ORM models
│   ├── rag/
│   │   └── pipeline.py             # ChromaDB + Embeddings RAG
│   ├── routes/
│   │   ├── api.py                  # REST API endpoints
│   │   ├── auth.py                 # Authentication routes
│   │   ├── dashboard.py            # Dashboard routes
│   │   └── main.py                 # Landing page routes
│   ├── services/
│   │   └── watsonx_service.py      # IBM Granite AI integration
│   ├── static/
│   │   ├── css/smartkrishi.css     # Full UI stylesheet (dark mode)
│   │   └── js/
│   │       ├── app.js              # Core JS (dark mode, voice, i18n)
│   │       ├── chat.js             # Chat interface JS
│   │       └── landing.js          # Landing page JS
│   └── templates/
│       ├── base.html               # Base template with navbar
│       ├── index.html              # Landing page
│       ├── auth/                   # Login + Register
│       ├── dashboard/              # All dashboard pages
│       └── partials/               # Reusable components
├── data/
│   ├── knowledge_base/             # Add custom .txt/.json docs here
│   └── vector_store/               # ChromaDB persisted vectors
├── docs/
│   └── IBM_CLOUD_DEPLOYMENT.md     # 📚 Full deployment guide
├── docker/
│   └── nginx.conf                  # Nginx reverse proxy config
├── .env.example                    # Environment template
├── Dockerfile                      # Production Docker image
├── docker-compose.yml              # Full stack (app + db + redis + nginx)
├── requirements.txt                # Python dependencies
└── run.py                          # Application entry point
```

---

## 🚀 Quick Start (5 minutes)

### 1. Clone and Setup
```bash
git clone <repo-url>
cd SmartKrishi
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 2. Configure IBM watsonx.ai
Edit `.env`:
```env
IBM_CLOUD_API_KEY=your-ibm-cloud-api-key
WATSONX_PROJECT_ID=your-watsonx-project-id
```
Get these from [cloud.ibm.com](https://cloud.ibm.com) — see `docs/IBM_CLOUD_DEPLOYMENT.md`

### 3. Run
```bash
python run.py
# → Open: http://localhost:5000
# → Demo login: click "Try Free Demo"
```

### 4. Docker (Production-ready)
```bash
docker-compose up -d
# → Open: http://localhost:5000
```

---

## 🔧 Customizing the AI Agent

Edit [`app/agent_instructions.py`](app/agent_instructions.py) to change:

| Section | What it controls |
|---------|-----------------|
| `AGENT_PERSONA` | Who the AI is — name, expertise areas |
| `AGENT_TONE` | How it speaks — formal/informal, language rules |
| `AGENT_EXPERTISE` | What domains it prioritizes |
| `AGENT_SAFETY_RULES` | What it must NEVER do |
| `AGENT_RESPONSE_FORMAT` | How it structures answers |
| `AGENT_RAG_INSTRUCTIONS` | How it uses the knowledge base |
| `AGENT_CRISIS_RESPONSE` | How it handles distress situations |
| `PROMPT_TEMPLATES` | Pre-built prompts for specific use cases |
---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat` | Main AI chat (RAG-powered) |
| GET | `/api/weather` | Weather forecast + farming advisory |
| GET | `/api/mandi-prices` | Live mandi prices from agmarknet |
| POST | `/api/soil-analysis` | AI soil interpretation |
| POST | `/api/crop-recommendation` | Crop recommendations |
| GET | `/api/schemes` | Government scheme information |
| POST | `/api/translate` | Text translation |
| GET/PUT | `/api/profile` | Farmer profile management |
| GET | `/health` | Health check endpoint |

---

## 🏛️ Adding Knowledge to RAG

Add farming documents to the vector store:

```python
from app.rag.pipeline import vector_store, doc_processor

# Add a text file
chunks = doc_processor.process_text_file("data/knowledge_base/my_guide.txt", category="pest")
vector_store.add_documents_batch(chunks)

# Add structured JSON
docs = doc_processor.process_json_knowledge("data/knowledge_base/schemes.json")
vector_store.add_documents_batch(docs)
```

---

## 🛡️ Security Features

- Password hashing with bcrypt
- CSRF protection on all forms
- Rate limiting (30 req/min per IP)
- HTTP security headers via Nginx
- Non-root Docker container
- Environment-based secrets (never in code)
- SQL injection prevention via SQLAlchemy ORM

---

## 🚨 Emergency Helplines (Built into AI)

The AI agent automatically provides:
- **Kisan Call Centre**: 1800-180-1551 (24×7, all languages)
- **PM-KISAN Helpline**: 155261
- **PM Fasal Bima Yojana**: 1800-200-7710

---

 Free to use, modify, and deploy. Built with ❤️ for Indian farmers.

---

*SmartKrishi is an advisory tool. Always consult local agricultural experts for critical farming decisions.*
