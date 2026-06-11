# Cloud image: runs the agent worker + web server (see scripts/start.sh).
# Phone -> LiveKit Cloud (media) ; this container -> LiveKit Cloud + OpenAI + Neon.
FROM python:3.11-slim

# onnxruntime (silero VAD / turn detector) needs libgomp.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV PYTHONPATH=/app/src PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Pre-download VAD / turn-detector models at build (best effort; degrades to VAD).
RUN python -m visitor_agent.agent download-files || true

EXPOSE 8080
CMD ["bash", "scripts/start.sh"]
