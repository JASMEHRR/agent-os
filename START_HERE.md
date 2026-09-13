# Post Studio

Five small agents behind one home screen. Open it and they are listed; click
one to go in.

| | What it does | What it needs |
|---|---|---|
| **Posts** | You write what you did this week; it drafts a LinkedIn post, a newsletter and an article from the same facts. | A free Groq key |
| **Inbox** | Reads your new mail, works out what actually matters, and texts you about that only. | Sign in with Google |
| **Apply** | Competitions and internships, tracked through their stages, with a nudge before each closes. | Nothing |
| **Classwork** | What is still to hand in, from Google Classroom. | Sign in with Google |
| **Automatic** | Shows what each of the others is doing on its own, when it last ran, and what it found. | Nothing |

Nothing is published, sent or texted without you. Posts asks before anything
reaches LinkedIn; Inbox only ever reads, never sends or deletes; Classwork is
read-only by the permission Google itself enforces.

---

## First time: one minute

### 1. Open it

Double-click **`PostStudio.bat`**.

A black window appears (leave it open) and your browser opens the studio.
**You do not need to set anything up first.** It opens with nothing
configured, and tells you what is missing.

### 2. Press Connect

The **Connect** app is where everything gets hooked up — no text editor, no
files to find. Each box says what it is for and where to get it.

- **A model.** Free Groq key from **https://console.groq.com/keys**. Starts
  with `gsk_`. No card. Posts needs this; nothing else does.
- **Google.** One sign-in, the normal Google prompt, covers both Inbox and
  Classwork. It asks for read-only, which is enforced by Google rather than
  promised by this program, and you can take it back in one click at
  myaccount.google.com/permissions.
- **Your name.** Worth doing before anything else. Without it, drafts are
  written for "the person using this" rather than for you.
- **WhatsApp**, if you want the Inbox agent to text you rather than print.

Restart the studio after saving, and what you connected turns on.

Everything you paste there goes into a `.env` file next to the app, which is
ignored by git. Nothing is ever sent anywhere except the service it belongs
to, and the Connect screen never shows a saved secret back to you — so a key
in a box always means a key you just typed.

### 3. Let it run on its own

The agents check on their own while the studio is open: mail every five
minutes, deadlines every six hours, classwork every three. The **Automatic**
tab shows each one — when it last ran, what it found, and buttons to run it
now or pause it.

To keep them running when the studio is **closed**:

```bash
python scripts/watch.py
```

No window, no browser. On Windows, Task Scheduler → "When I log on" → run
`pythonw scripts\watch.py` and it starts with your computer. Running it at
the same time as the studio is fine: they agree between themselves which one
does the work, so you never get texted twice about one email.

---

## Using Posts

1. **Press "Pull this week from my git."** The box fills itself from your
   commit messages. Or type what you did, or press "Speak it instead" and talk.
2. **Tick the channels** you want. LinkedIn is on by default.
3. **Press "Write my drafts."** Takes 10 to 30 seconds.
4. **Read what comes back** on the Review tab. Approve the ones you like,
   discard the rest. Approving copies the text so you can paste it straight in.
5. **Press "Sounds like me"** on any draft that does. That draft becomes an
   example every future draft is written against. Press "Not me" on the
   ones that do not, and it will not learn from them.

That is the whole thing. The more you rate, the less you have to edit.

### Teaching it your voice faster

The **Voice** tab takes posts you have written or refined. Paste one, pick
the channel, add it. Five good examples changes the output more than any
amount of rules, and it keeps working after the model underneath changes,
because the examples travel with every prompt.

Only text you approve ever gets in. It cannot learn from its own unrated
drafts, so it learns you rather than itself.

### People

The **People** tab drafts a personalised note to someone worth knowing. You
give the name and the specific reason (a talk, a project, a post). It writes
the note; you send it. There is no send button, because LinkedIn has no API
for invitations and automating that gets accounts restricted.

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

## Using the other three

### Inbox

It reads new mail and decides, for each one, whether it is worth interrupting
you. **Urgent** texts you immediately, even at two in the morning. **Important**
texts you too, unless it is quiet hours or you have already had your hourly
share — then it waits, and the "send digest" button sends everything waiting as
one message. **Routine** and **bulk** never text you at all; routine still shows
on the tab so you can see what it decided.

**It will get some of these wrong at first, and the fix is the filter box.**
Tell it what you want and what you do not — "always tell me about anything
from the placement cell", "never tell me about anything with 'webinar' in the
subject" — and your rules beat its scoring every time. Each rule shows how
many times it has fired, so you can see which are doing work.

It never sends, deletes or marks anything. It cannot: the permission it asks
Google for does not include those.

Two settings worth knowing, both in Connect: **quiet hours** (11pm to 7am by
default, when nothing buzzes) and **most texts per hour** (six). The second
one exists because an agent that can text you is an agent that can text you
forty times, and a cap is the only real protection against that.

Before you let it text you, leave it a day on the Inbox tab and read the
decisions. It shows every one it made and why.

### Apply

Add anything you might go for — a competition, an internship, a certification
— with its closing date. It tracks which stage each one is at and reminds you
before the date, once per rung: a week out, three days, the day before, the
day itself. Never twice for the same rung, which is the difference between a
reminder and a nag.

Moving something to "applied" stops the closing reminders, because once you
have applied the date is no longer something you can act on.

### Classwork

Reads Google Classroom, read-only, and shows what is still to hand in with how
long you have. It nudges before each is due and marks anything already overdue.
Turn work in on Classroom as normal; this catches up on its next check.

---

## When something goes wrong

**"No model connected yet"** in the black window
: Expected on a fresh copy — it opens anyway. Put a Groq key in the Connect
  app and restart. Everything except drafting works without one.

**A tab is missing from an app**
: That agent is not connected yet. A tab that is not wired up is hidden rather
  than shown empty, because an empty screen reads as "nothing to do".

**The Automatic tab says something else is running these**
: `scripts/watch.py` is running in the background and has the jobs. That is
  working as intended. Stop it and this window picks them up within a minute.

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
| Everything you have written, rated, tracked and been alerted about | `agent.db` (git-ignored, survives restarts) |
| Your API keys | `.env` (git-ignored, never committed) |
| The voice rules | `services/content_agent/content_agent/voice.py` |
| The per-channel rules | `services/content_agent/content_agent/formats.py` |

If a post reads wrong, the fix is usually in `voice.py`. The rules there are
enforced in code rather than asked for in a prompt, which is why they hold
after a model gets swapped underneath.

---

## What it deliberately does not do

- **It does not publish anything you have not approved.** It can post now, and
  it can post at a time you choose, but only a draft you personally approved.
  There is no auto-approve, no timeout that counts as a yes, and no setting
  that turns one on. The refusal is structural: a draft can only reach
  "published" from "approved", so a bug in the scheduler cannot route around
  it.
- **It does not invent numbers.** Every figure comes from your note.
- **It does not decide what to post.** It decides when, and only after you
  have said yes to what.

The first one is the design decision the rest of this hangs off, and it is the
one I would push back hardest on changing.
