FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
RUN uv pip install --system --no-cache .

COPY src/ ./src/
COPY data/ ./data/

ENV PORT=8080
# `streamlit run src/ui/app.py` puts src/ui/ on sys.path[0], not /app — without this,
# `from src.agents...` etc. raise ModuleNotFoundError. Fixed after hitting it on first deploy.
ENV PYTHONPATH=/app
EXPOSE 8080

# Single Cloud Run container running the Streamlit UI (plan.md Structure Decision —
# Principle V: one deployable service, not split frontend/backend).
CMD ["sh", "-c", "streamlit run src/ui/app.py --server.port=${PORT} --server.address=0.0.0.0 --server.headless=true"]
