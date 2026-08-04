FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY pyproject.toml ./
COPY app ./app
RUN pip wheel --wheel-dir /wheels .

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/home/emily/.local/bin:${PATH}"

RUN groupadd --system --gid 10001 emily \
    && useradd --system --uid 10001 --gid emily --create-home emily

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

WORKDIR /app
COPY --chown=emily:emily app ./app
RUN mkdir /data && chown emily:emily /data

USER emily
EXPOSE 8787

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8787", "--no-access-log"]

FROM runtime AS test
USER root
COPY pyproject.toml ./
COPY tests ./tests
RUN pip install --no-cache-dir '.[dev]'
USER emily
CMD ["pytest"]

FROM runtime AS final
