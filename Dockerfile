FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY src/ ./src/

# Never run as root: a compromised dependency would otherwise own the container.
RUN useradd --create-home --uid 10001 bot
USER bot

CMD ["python", "main.py"]
