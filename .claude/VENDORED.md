# linkedin-skills, vendored

Third-party skills, not written here. Source:

| | |
|---|---|
| Repository | https://github.com/sergebulaev/linkedin-skills |
| Commit | `4b499e736491aab4f9f53ed9ec390853391fceb9` (2026-09-05) |
| Version | 1.0.26 |
| Licence | MIT, see `LICENSE` |

## Why it is here rather than installed as a plugin

Upstream ships this as a Claude Code plugin, and on a laptop the one-command
install is the right one:

```
/plugin marketplace add sergebulaev/linkedin-skills
/plugin install linkedin-skills@linkedin-skills
```

That writes into `~/.claude`, which a cloud session throws away when its
container is reclaimed. Committed here instead, the skills are present in every
checkout, including the ones the weekly routine runs in.

## Layout

The bundle root maps onto `.claude/`, so the paths inside the skills resolve
unchanged: `references/`, `lib/` and `scripts/` sit beside `skills/`, and a
skill reaching `../../references/hook-formulas.md` finds it. Excluded from the
copy: `.codex-marketplace/` (a duplicate of the same skills for Codex),
`assets/` (a 792K banner), `.github/`.

One file was edited. Upstream's bundle-level `SKILL.md` sat at the repository
root and used root-relative paths; it is now
`skills/linkedin-marketing/SKILL.md`, one level deeper, so those paths were
rewritten to `../../`. Nothing else was changed, and no reference resolves any
worse than it does upstream.

## What these skills expect, and what this repository does not do

They publish. `linkedin-post-writer`, `linkedin-comment-drafter` and
`linkedin-reply-handler` send approved text to LinkedIn through the Publora
API, and `linkedin-engager-analytics` and `linkedin-thread-monitor` scrape it
through Apify. Post Studio deliberately has no publish verb, so these are the
opposite decision, taken by someone else. They are inert without credentials:

| Variable | Needed for |
|---|---|
| `PUBLORA_API_KEY`, `LINKEDIN_PLATFORM_ID` | publishing anything |
| `APIFY_TOKEN` | reading post bodies, likers, commenters |
| `PIXFARO_TOKEN` | generating illustrations |

Set none of them and every skill still drafts; only the send step fails. See
`.env.example`. Their Python needs `requests` and `python-dotenv`
(`requirements.txt`), neither of which the rest of this repository uses.

The CI gates do not read any of this: ruff and pytest are pointed at
`libs services tests`, and mypy skips dot-directories.

## Overlap with the voice gates

These skills carry their own voice rules, hook formulas and humanizer, written
for a general LinkedIn audience. `services/content_agent/content_agent/voice.py`
carries yours, enforced in code. Where the two disagree, the gates win, because
they are the ones that can reject a draft.
