# Stage 1: build
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: runtime
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN useradd --uid 10001 --no-create-home appuser
WORKDIR /app
COPY --from=builder /install /usr/local
COPY --chown=10001:10001 manage.py ./
COPY --chown=10001:10001 config/ ./config/
COPY --chown=10001:10001 orders/ ./orders/
USER 10001
EXPOSE 8080
# --worker-tmp-dir /dev/shm: gunicorn heartbeat files go to memory (works with read-only root fs)
ENTRYPOINT ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8080", \
            "--workers", "2", "--threads", "2", "--worker-tmp-dir", "/dev/shm", \
            "--access-logfile", "-"]
