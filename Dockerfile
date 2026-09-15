FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app/src
RUN apt-get update && apt-get install -y --no-install-recommends adb ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 duomove
WORKDIR /app
COPY requirements.lock .
RUN python -m pip install --no-cache-dir -r requirements.lock
COPY src ./src
USER duomove
EXPOSE 8000
CMD ["python", "-m", "duomove", "serve"]
