# Bolo: one container runs the intake agent (internal :9000) and the voice app (:8000). No API keys needed to start.
FROM python:3.12-slim

# ffmpeg converts browser audio (webm/ogg) to 16 kHz WAV for server-side speech-to-text.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /bolo
COPY app/requirements.txt app/requirements.txt
# faster-whisper is the default speech-to-text for the phone-call screen: it runs on CPU and needs no key.
RUN pip install --no-cache-dir -r app/requirements.txt faster-whisper==1.2.1

COPY . .
# Repos already cloned on Windows may have CRLF line endings; sh would fail on them.
RUN sed -i 's/\r$//' deploy/start.sh
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["sh", "deploy/start.sh"]
