# Posting to LinkedIn from here

`scripts/linkedin_post.py` publishes to your own feed through LinkedIn's own
API. It is free, it is the route LinkedIn supports, and the token lives on your
machine rather than with a company in the middle.

Post Studio uses this too. Once you have run `auth` below, the Review tab can
send a draft you approved, or hold it until a time you pick and let
`scripts/publish_due.py` send it then. Approving is still the only way anything
reaches LinkedIn, and this file is still usable on its own for a post that
never went through the studio.

## Once: make the app (about ten minutes)

1. Go to **https://www.linkedin.com/developers/apps** and choose **Create app**.
   It asks for a LinkedIn Page to associate; any page you control works, and
   you can make one in a minute if you have none.
2. On the app's **Products** tab, request both:
   - **Sign In with LinkedIn using OpenID Connect**
   - **Share on LinkedIn**

   Both are self-serve and usually granted immediately. The first is what lets
   the tool learn your member id, which every post has to name as its author.
   The second is permission to post.
3. On the **Auth** tab:
   - copy the **Client ID** and **Client Secret**
   - under **Authorized redirect URLs**, add exactly:
     `http://localhost:8770/callback`

     It has to match character for character or LinkedIn refuses the sign-in.
4. Put the two values in `.env` beside the repo:

   ```
   LINKEDIN_CLIENT_ID=your_client_id
   LINKEDIN_CLIENT_SECRET=your_client_secret
   ```

## Once: connect your account

```bash
python scripts/linkedin_post.py auth
```

Your browser opens, you approve the app, the tab says it is done. The token is
written to `.linkedin.json` in the repository root, readable only by you and
ignored by git.

Check it whenever you are unsure what is set up:

```bash
python scripts/linkedin_post.py check
```

**Tokens expire, roughly every two months.** `check` tells you how many days
are left. When it runs out, run `auth` again. Refresh tokens are only issued to
apps LinkedIn has reviewed, so re-running the one command is the honest answer
rather than pretending otherwise.

## Posting

```bash
# see exactly what would be sent, send nothing
python scripts/linkedin_post.py post --file drafts/2026-09-02.md --dry-run

# actually post
python scripts/linkedin_post.py post --text "the post itself"
python scripts/linkedin_post.py post --file post.txt
cat post.txt | python scripts/linkedin_post.py post
```

`--dry-run` first, every time. It is the only step between a draft and five
thousand people.

## Sending on a schedule

Approve a draft in Post Studio's Review tab, give it a time, and it sits in
the queue. Something has to be running to send it, and that something is:

```bash
python scripts/publish_due.py            # send anything due now
python scripts/publish_due.py --list     # show the queue, send nothing
python scripts/publish_due.py --dry-run  # say what would go, send nothing
```

It sends what is due and exits, so it needs to be run repeatedly. On Windows,
Task Scheduler:

1. Open **Task Scheduler**, choose **Create Task** (not the basic wizard).
2. **Triggers**: new trigger, daily, and tick **Repeat task every 15 minutes**
   for a duration of **Indefinitely**.
3. **Actions**: start a program, `python`, with arguments
   `scripts\publish_due.py`, and **Start in** set to this repository's folder.
   The "start in" matters: without it the script cannot find `agent.db`.
4. **Conditions**: untick "start only if on AC power" if you want it to run on
   battery.

Fifteen minutes is deliberate. A post landing at 9:07 rather than 9:00 costs
nothing, and a schedule that fired every minute would spend the day opening a
database to find it empty. Nothing is lost while the laptop is asleep either:
a post that was due stays due, so the first run after it wakes sends what was
missed rather than skipping it.

A failed send lands the draft in "publish failed" with the reason attached,
where the Review tab shows it. It keeps its time and is retried on the next
run, so a dead network costs a delay rather than an approval.

## Wiring it into the linkedin-skills bundle

The vendored skills publish through Publora by default. Point them here
instead:

```
LINKEDIN_SKILLS_CUSTOM_POSTER=python /full/path/to/scripts/linkedin_post.py poster
```

The bundle appends the kind and the target URL, hands the draft over as JSON,
and reads back JSON. Posts, comments and replies go through LinkedIn. A
reshare is refused rather than quietly published as something else.

**Do not set `LINKEDIN_PLATFORM_ID`.** That is the bundle's own signal that
Publora is configured, and it makes the bundle route there before this poster
is ever called.

## Publora as the backup

Optional, and only used when the LinkedIn call cannot run: no token yet, an
expired one, or LinkedIn itself refusing. Set both:

```
PUBLORA_API_KEY=sk_...
PUBLORA_PLATFORM_ID=linkedin-...
```

`PUBLORA_PLATFORM_ID` rather than the bundle's `LINKEDIN_PLATFORM_ID`, for the
reason above: this way LinkedIn stays first and Publora is genuinely the
fallback. When a post goes out this way it says so.

## When something breaks

| What you see | What it means |
|---|---|
| `401` | The token expired or was revoked. Run `auth` again. |
| `403` | A product is missing from the app. Add both from step 2, then re-run `auth` so the new permissions are on the token. |
| `426`, or a `400` mentioning the version | The API version is retired. Set `LINKEDIN_API_VERSION` to a current `YYYYMM` from [the versioning page](https://learn.microsoft.com/en-us/linkedin/marketing/versioning). |
| `429` | Rate limited. Wait. |

## The two dates that expire

**The API version.** LinkedIn supports each `YYYYMM` version for about a year
and then sunsets it. The default here is `202608`. When it stops being
accepted, one environment variable fixes it, and the error says exactly that.
This is not hypothetical: the first version shipped in this file was `202508`,
which LinkedIn sunset on 17 August 2026, so it was already dead on arrival.

**Your token.** About two months. `check` counts down.

## Why the post body gets backslashes added to it

The versioned Posts API reads the body as
[little text](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/little-text-format),
where `_ | ( ) [ ] { } @ # * ~ < > \` are markup. LinkedIn's rule is that every
one of them is escaped whether or not you meant it as markup.

This matters more than it sounds. An unescaped bracket does not render oddly,
it **truncates the post at that point**, so half your post publishes and looks
like you meant it. The tool escapes them for you.

`LINKEDIN_ESCAPE=0` exists for a future format change, not as a preference.
Turning it off is how you get the truncation.

## What this deliberately does not do

- **Scrape.** Reading other people's likers and commenters is not something
  LinkedIn's API offers, and the workarounds are against their terms.
- **Drive a browser.** That is the route that ends in a restricted account.
- **Post without you.** Every path here starts with you running a command.
