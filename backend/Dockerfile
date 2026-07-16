# DeployUnit backend — web tier.
# Runs the FastAPI app with the in-process scheduler ON (default), so a single
# container serves the API and runs all periodic jobs. If you scale to
# multiple web replicas, set DISABLE_SCHEDULER=1 on the web containers and run
# ONE worker separately (see Dockerfile.worker / `python worker.py`).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
# Drop dev-only tooling to keep the image lean.
RUN grep -viE '^(black|isort|flake8|mypy|pytest)\b' requirements.txt > runtime-requirements.txt \
    && pip install -r runtime-requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
