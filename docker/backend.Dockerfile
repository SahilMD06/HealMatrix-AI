FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Core runtime only by default: fast build, small image, fits a free-tier host.
# Build with --build-arg INSTALL_AI=true to add the LangGraph/CrewAI/RAG stack,
# which pulls PyTorch and takes the image well past 1.5 GB.
ARG INSTALL_AI=false

COPY requirements.txt requirements-ai.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && if [ "$INSTALL_AI" = "true" ]; then pip install -r requirements-ai.txt; fi

COPY . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
