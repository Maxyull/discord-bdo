FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY src/ ./src/

# Never run as root: a compromised dependency would otherwise own the container.
RUN useradd --create-home --uid 10001 bot \
 && mkdir -p /app/data \
 && chown -R bot:bot /app/data
USER bot

# The setup cards live here; docker-compose mounts a named volume over it so a
# rebuild does not wipe them.
VOLUME ["/app/data"]

CMD ["python", "main.py"]
