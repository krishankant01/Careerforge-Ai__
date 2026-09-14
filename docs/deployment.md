# Deployment Guide

CareerForge AI is fully containerized and production-ready.

## Prerequisites
- Docker Engine & Docker Compose
- (Optional) NVIDIA drivers + NVIDIA Container Toolkit for GPU acceleration if using local Ollama.

## Environment Variables
Create a `.env` file in the root directory:
```bash
cp .env.example .env
```
Ensure you set a strong `JWT_SECRET` and `GITHUB_TOKEN_ENCRYPTION_KEY` (use `openssl rand -hex 32`).

## Deploying via Docker Compose

The `docker-compose.yml` file defines 3 services:
1. `postgres`: Runs `pgvector/pgvector:pg16`.
2. `backend`: The FastAPI application.
3. `frontend`: The React SPA served via Nginx.
(Optional: uncomment the `ollama` service if you are hosting the LLM locally).

Run the stack in detached mode:
```bash
docker-compose up -d --build
```

### Checking Logs
```bash
docker-compose logs -f
```

## Scaling and Cloud Providers

For large-scale production deployments (AWS, Render, Heroku):
1. **Database**: Use a managed PostgreSQL instance (like AWS RDS or Supabase) that supports the `pgvector` extension.
2. **Backend**: Deploy the backend Docker container to a managed container service (AWS ECS, Render Web Service). Pass the `DATABASE_URL` as an environment variable.
3. **Frontend**: Deploy the built React app (`dist/`) to Vercel, Netlify, or AWS CloudFront/S3. Ensure you set the `VITE_API_URL` during build time.
4. **LLM**: Switch `LLM_PROVIDER` in the backend `.env` from `ollama` to `anthropic` or `openai` to use managed, highly available models instead of local inference.
