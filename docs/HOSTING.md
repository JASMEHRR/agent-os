# Hosting Post Studio

Running it on your laptop is the default and needs no login: only your machine
can reach it. Hosting it means anyone with the URL can reach it, so the hosted
copy requires a password, and that password is the switch.

Set `STUDIO_PASSWORD` and the server binds every interface and demands a
login cookie on every `/api` route. Leave it unset and it binds loopback and
asks nothing. There is no third mode.

## The honest constraint: free hosts wipe their disk

Every free tier restarts your container and gives it a fresh filesystem.
`agent.db` holds your notes, drafts, samples and persona. On a free host
without a persistent volume, all of it is gone at the next restart, which can
be daily.

| Host | Free tier | Keeps `/data` across restarts | Card needed |
|---|---|---|---|
| Hugging Face Spaces (Docker) | yes | no, unless you pay for persistent storage | no |
| Render (web service) | yes, sleeps after 15 min idle | no, disks are paid | no |
| Fly.io | small allowance | yes, volumes are free within the allowance | yes |
| Your laptop | yes | yes | no |

So the recommendation is unglamorous: **run it on your laptop, and let the
weekly cloud routine be the part that runs while you are away.** The routine
already reads `voice/persona.md` and `voice/samples.md` from the repository,
which `scripts/publish_voice.py` writes. That combination is free, durable,
and needs no password because nothing is exposed.

Host it only if you want to use it from your phone. Then:

## Hugging Face Spaces, no card

1. Create a Space, type **Docker**, visibility **private**.
2. Push this repository to it (Spaces are git repositories).
3. In Settings, add a secret `STUDIO_PASSWORD`. Choose a real one; it is the
   only thing between the internet and your drafts.
4. Add `GROQ_API_KEY` as a secret too.
5. It builds from the `Dockerfile` and serves on port 7860.

Accept that the database resets. Run `scripts/publish_voice.py` from your
laptop so the persona and samples live in the repo, and treat the hosted copy
as a phone-friendly front end rather than the system of record.

## What the hosted copy cannot do

- **Pull from git.** The container has no checkout of your other repos.
  `REPOS` would have to point at paths inside the container, which means
  cloning them in the Dockerfile with a token, which is more surface than a
  drafting tool should carry. Use the button on your laptop.
- **Survive a restart** without a paid volume. See above.

## Security notes for the hosted copy

- One password, one user, no accounts. The cookie is derived from the
  password, so changing the password logs every session out.
- Cookie is `HttpOnly` and `SameSite=Strict`. The host's TLS proxy supplies
  `Secure`; do not host it without TLS.
- The Origin check stays on: a cross-site form POST still cannot approve or
  discard your drafts.
- Nothing publishes. Same as local: there is no function that posts anywhere.
