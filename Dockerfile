# Post Studio, hosted.
#
# Nothing to install: the repository has no runtime dependencies, so the
# image is the Python base plus the source. The one thing a host must give
# it is STUDIO_PASSWORD; without that the server binds loopback and the
# platform's proxy cannot reach it, which is the correct failure for a
# hosted copy with no login configured.
#
# Data lives in /data/agent.db. Mount a persistent volume there or the
# host's restart wipes every note, draft, sample and fact. See docs/HOSTING.md.

FROM python:3.11-slim

WORKDIR /app
COPY . /app

# git is needed for the "pull this week from my git" button. The repos it
# reads are whatever REPOS points at inside the container; on a host with
# nothing mounted the button reports "not a git repository" rather than
# failing, which is the honest answer.
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    DB_PATH=/data/agent.db \
    PORT=7860

VOLUME ["/data"]
EXPOSE 7860

CMD ["python", "scripts/serve.py"]
