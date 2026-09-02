# Post Studio, hosted. START_HERE.md, "Hosting it", walks through using this.
#
# On a laptop nothing here is needed: double-click PostStudio.bat. This is for
# a copy that lives at a URL, where the studio needs a password
# (POST_STUDIO_PASSWORD) and reads your other repositories from clones
# (REPO_URLS) rather than from the folders beside it.
FROM python:3.11-slim

# git: "pull this week from my git" reads commit history, and REPO_URLS is
# cloned with it.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# The only third-party package on the studio's import path.
RUN pip install --no-cache-dir pydantic

# Named after the repository, so a clone of it under REPO_URLS is recognised
# as the same one and not read twice.
WORKDIR /app/agent-os
COPY . .

ENV POST_STUDIO_HOST=0.0.0.0 \
    POST_STUDIO_DATA=/data \
    PORT=8765 \
    PYTHONUNBUFFERED=1

# agent.db and the clones. Mount a disk here to keep them across deploys.
VOLUME ["/data"]
EXPOSE 8765

CMD ["python", "scripts/serve.py"]
