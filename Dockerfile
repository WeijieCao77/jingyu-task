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

# Normalize line endings: if the build context came from a Windows checkout,
# scripts/start.sh may have CRLF, which makes the container's bash choke on the
# trailing \r ("set: pipefail: invalid option name" → crash loop). Strip CR.
RUN sed -i 's/\r$//' scripts/start.sh

# Pre-download VAD / turn-detector models at build (best effort; degrades to VAD).
RUN python -m visitor_agent.agent download-files || true

EXPOSE 8080
CMD ["bash", "scripts/start.sh"]
