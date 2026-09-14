# CareerForge AI 🚀

CareerForge AI is an advanced, AI-powered Career & Code Intelligence platform designed to help software engineers navigate their careers. It analyzes resumes, identifies skill gaps, reviews GitHub repositories, and conducts dynamic mock interviews using a sophisticated multi-agent LangGraph architecture.

## 🌟 Key Features
- **Intelligent RAG Resume Parsing**: Chat directly with your career history.
- **Job Matching & Skill Gap Analysis**: Compares your resume against target jobs.
- **GitHub Code Intelligence**: Syncs repositories and provides automated, LLM-driven code reviews.
- **Multi-Agent Orchestration**: Powered by LangGraph, specialized agents collaborate to provide personalized project recommendations, learning roadmaps, and mock interviews.
- **SaaS-Ready UI**: A highly polished, responsive dashboard built with React, Vite, and Tailwind CSS.

## 🛠️ Technology Stack
- **Frontend**: React, TypeScript, Vite, Tailwind CSS, Framer Motion, Vitest.
- **Backend**: FastAPI, Python 3.11+, SQLAlchemy, asyncpg, Pytest, SlowAPI.
- **Database**: PostgreSQL with `pgvector` extension for high-performance vector search.
- **AI/LLM**: LangChain, LangGraph, Ollama (Local), Anthropic (Cloud).

## 🚀 Quickstart (Local Development)

### 1. Database & Environment
Start the local pgvector database:
```bash
docker-compose up -d postgres
```
Copy the environment variables:
```bash
cp .env.example .env
```

### 2. Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

## 🚢 Production Deployment
The entire stack is containerized for production:
```bash
docker-compose up -d --build
```
This builds a multi-stage Nginx container for the frontend and a secure non-root container for the backend.

## 📚 Documentation
For detailed insights into the system design, see the `/docs` directory:
- [Architecture](docs/architecture.md)
- [Database](docs/database.md)
- [Agents](docs/agents.md)
- [RAG Pipeline](docs/rag.md)
- [API](docs/api.md)
- [Deployment](docs/deployment.md)

## 🧪 Testing
```bash
# Backend tests
cd backend && pytest

# Frontend tests
cd frontend && npm run test
```
