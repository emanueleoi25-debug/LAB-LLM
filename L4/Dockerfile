# Base comune: Python 3.14 e dipendenze dell'applicazione.
FROM python:3.14.9-slim AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Test automatici su Python 3.14 (docker compose --profile test run --rm --build test).
FROM base AS test
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY pytest.ini .
COPY assistente/ assistente/
COPY tests/ tests/
CMD ["python", "-m", "pytest", "-p", "no:cacheprovider"]

# Applicazione (ultimo stage, quindi predefinito): niente test né pytest.
FROM base AS app
COPY assistente/ assistente/
RUN useradd --create-home --uid 1000 assistente
USER assistente
CMD ["python", "-m", "assistente"]
