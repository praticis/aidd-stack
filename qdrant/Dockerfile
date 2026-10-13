# Versions are pinned (base image and package) — bump deliberately.
FROM python:3.12.15-slim

EXPOSE 3000
WORKDIR /app

# Optimizations for Python behavior inside Docker
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN pip install mcp-server-qdrant==0.8.1

CMD ["python", "run-mcp.py"]