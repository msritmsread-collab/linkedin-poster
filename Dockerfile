# Multi-stage build: Node (React) + Python (FastAPI)
# Target: Google Cloud Run

# ── Stage 1: Build React frontend ────────────────────────────────────────────
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json .
RUN npm install

COPY frontend/ .
RUN npm run build


# ── Stage 2: Python runtime ───────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

RUN mkdir -p data/images

ENV PORT=8080

EXPOSE 8080

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port $PORT"]
