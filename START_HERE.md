# Post Studio

Write what you did this week. It drafts a LinkedIn post, a newsletter issue and
a Dev.to article from the same facts. You read them and decide what goes out.

Nothing is ever published automatically. It cannot be: the code has no verb
that posts anything anywhere.

---

## First time: two minutes

### 1. Get a free Groq key

Go to **https://console.groq.com/keys**, sign in, create a key. It starts with
`gsk_`. Free, no card.

### 2. Put it in a file

In this folder there is a file called `.env.example`. Make a copy of it named
exactly `.env`, open it in Notepad, and paste your key after the `=`:

```
GROQ_API_KEY=gsk_your_key_here
```

No quotes. No spaces around the `=`. Save it.

`.env` is ignored by git, so the key never leaves your machine.

### 3. Open it

Double-click **`PostStudio.bat`**.

A black window appears (leave it open) and your browser opens the studio. If
the browser shows an error for a second, refresh it: the server takes about a
second to start.

---

## Using it

1. **Type what you did this week** in the big box. Plain sentences. Include
   real numbers if you have them.
2. **Tick the channels** you want. LinkedIn is on by default.
3. **Press "Write my post."** Takes 10 to 30 seconds.
4. **Read what comes back.** Approve the ones you like, discard the rest.
   Approving copies the text to your clipboard so you can paste it straight in.

That is the whole thing.

### What makes a good note

Bad: *"worked on the project"*

Good: *"Wired Groq behind the model router. Took 3 attempts because the free
tier rate limits at 429 rather than billing you, so I built a cooldown that
degrades to a smaller model. Suite is at 1834 tests."*

The difference is that the second one has facts in it. **It will not invent
facts.** If your note has nothing specific, the draft gets rejected rather than
padded out with filler, because a post full of invented achievements is the
worst thing that could go on your real profile.

---

## When something goes wrong

**"No model configured"** in the black window
: The `.env` file is missing or the key is wrong. Check step 2.

**"That is too short to write from"**
: Your note needs a few more sentences. See "what makes a good note" above.

**A draft appears under "Did not work"**
: It could not satisfy the quality rules in three attempts. The reasons are
  listed. Usually the note had no concrete number in it.

**Everything is rate limited**
: Groq's free tier resets every minute. Wait a minute and try again. The system
  already degrades to a smaller model on its own before giving up.

**Check your key without showing it to anyone**

```bash
python scripts/diagnose_keys.py
```

Prints only the first four characters and the length, plus which models your
key can actually reach. Safe to share the output.

---

## The other way to run it

If you prefer a terminal:

```bash
python scripts/linkedin.py note
```

Then `draft`, then `review`. Same pipeline, same database.

To see the interface without using any API quota, with fixed example text:

```bash
python scripts/serve_demo.py
```

Opens on port 8766 instead, and uses its own `demo.db` so it cannot touch your
real drafts.

---

## Where things live

| What | Where |
|---|---|
| Your notes and drafts | `agent.db` (git-ignored, survives restarts) |
| Your API keys | `.env` (git-ignored, never committed) |
| The voice rules | `services/content_agent/content_agent/voice.py` |
| The per-channel rules | `services/content_agent/content_agent/formats.py` |

If a post reads wrong, the fix is usually in `voice.py`. The rules there are
enforced in code rather than asked for in a prompt, which is why they hold
after a model gets swapped underneath.

---

## What it deliberately does not do

- **It does not publish.** Not to LinkedIn, not anywhere. Approving marks a
  draft ready and copies it. You paste it yourself.
- **It does not invent numbers.** Every figure comes from your note.
- **It does not run unattended yet.** It runs when you open it.

The first one is a design decision and I would push back on changing it. The
third is the next thing worth building.
