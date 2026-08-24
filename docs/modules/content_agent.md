# Content Agent — Post Studio

**Stage:** A1 (application, first). Not a Build Specification stage.
**Status:** **Built and in use.**
**Modules:** `content_agent`

The first module built *on* the platform rather than as part of it. The
thirteen stages produced a control plane, and a control plane governs nothing
until something needs governing.

## What it does

Weekly notes in, gated drafts out, nothing published unasked.

```
capture(note) -> draft(note, channel) -> [gates] -> redraft, up to 3
                                                 -> DRAFTED, awaiting you
approve(draft, you) -> APPROVED
```

One note produces a LinkedIn post, a newsletter issue and a Dev.to article
from the same facts. Writing the note is the only part that cannot be
automated, because only the author knows what happened. Everything downstream
is reformatting.

## The vertical slice

| Layer | Used for |
|---|---|
| `llm_router` + `backends` | Inference on Groq and Gemini free tiers |
| `persistence.SQLiteRepository` | Notes and drafts surviving a restart |
| `voice` / `formats` | Quality gates, per channel |
| `drafts` | State machine with the approval boundary |
| `web` | Local interface, loopback only |

## Nothing publishes, four ways

This is the property the module exists to hold, so it is asserted four times
rather than once:

1. **`ContentStudio` holds no publishing verb.** Not `publish`, `post`,
   `send`, `share` or `submit`. A test checks the class surface, the same
   structural refusal the Evolution Gateway uses for `ratify`.
2. **`PUBLISHED` is reachable only from `APPROVED`**, asserted against the
   transition table itself rather than by walking a few paths. A test that
   tried some routes would pass while a newly added transition opened one
   nobody checked.
3. **Approval requires a named principal.** An anonymous approval is
   indistinguishable from no approval.
4. **The web server has no publish route**, checked from outside the studio,
   because an endpoint added later would not fail a test that only inspects
   the class.

## Gates rather than prompts

The voice rules exist as prose in the `linkedin-content` skill. Prose in a
prompt is advice: a model follows it most of the time, drifts on a bad
generation, and drifts further as models are swapped underneath. Over a
two-year unattended run that drift is the entire failure mode.

Everything checkable is checked. No em dashes. Hook under 140 characters so it
survives LinkedIn's "see more". One real number. Three to five niche hashtags.
No "humbled to announce". A failing draft is redrafted with the specific rule
named, bounded at three attempts, then kept in `REJECTED` with the outstanding
rules attached, because a repeated failure is information about the notes.

What is deliberately **not** gated: whether the post is any good. That is a
judgement, it belongs to the human at the approval gate, and a scoring
heuristic pretending otherwise would be a worse judge with more confidence.

### Three channels, three gate sets

The separation is the point. The rule that makes a LinkedIn hook work harms a
newsletter, where the subject is the hook and the body should breathe. One
shared set would have to be the loosest of the three, leaving the strictest
channel ungated.

| Channel | Gates beyond the universal ones |
|---|---|
| LinkedIn | hook truncation, hashtag count and breadth |
| Newsletter | subject under 60 chars, no throat-clearing opener, no hashtags |
| Dev.to | exactly 4 lowercase tags, markdown headings, no unclosed code fence |

Universal across all three: no em or en dashes, no clichés, at least one
concrete number. A channel added later inherits those by default rather than
by remembering to.

## A thin note is refused, not padded

A note with nothing specific in it produces a post full of invented
achievements, which is the worst failure available on a real profile. It is
refused at capture rather than after the model call, so the person is told
immediately and a free-tier request that was always going to fail is not spent.

## The local server

`http.server`, no dependencies, loopback only. It handles one request at a
time and is not a production server, which is correct for one person on
127.0.0.1 and wrong the moment it is not.

There is no authentication, so **reachability is the authorization**. Two
checks defend that:

- **Host**, against DNS rebinding. Loopback binding stops another machine
  connecting; it does not stop the reader's own browser being told to connect
  by a page that points a hostname it controls at 127.0.0.1.
- **Origin**, against cross-site writes. A cross-site form POST needs no
  preflight and could otherwise approve or discard drafts.

## Engineering Decisions recorded here

| Constant | Value | Why |
|---|---|---|
| `MAX_REDRAFTS` | 3 | first fix usually lands, second catches what it broke, third failure is a signal |
| `HOOK_TRUNCATION_CHARS` | 140 | roughly where LinkedIn hides the rest |
| `SUBJECT_MAX` | 60 | mail clients truncate past it |
| `DEVTO_TAG_COUNT` | 4 | Dev.to's own limit |
| `TOKEN_BUDGET` | 900 / 1400 / 2400 | a truncated draft fails the gates and burns two attempts fixing something the model did not do wrong |

## Open items

- **It does not run unattended.** It runs when opened. GitHub Actions on a
  cron is the free, no-KYC way to close this.
- **No publishing integration.** LinkedIn's API permits posting and reading
  your own post analytics under `w_member_social`. Connection requests and DMs
  are not available through it, and automating them violates the platform's
  terms, so the outreach half is manual by design rather than by omission.
- **No notifier**, so nothing says drafts are waiting.
- **No performance feedback loop.** The system cannot yet learn which posts
  worked, which is the thing that would make it improve rather than merely
  persist.
