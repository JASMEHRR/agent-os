# Posting to LinkedIn from here

`scripts/linkedin_post.py` publishes to your own feed through LinkedIn's own
API. It is free, it is the route LinkedIn supports, and the token lives on your
machine rather than with a company in the middle.

Post Studio still does not publish. This is a separate tool you run on purpose.

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
| `426` | The API version is retired. Set `LINKEDIN_API_VERSION` to a newer `YYYYMM` and try again. |
| `429` | Rate limited. Wait. |
| Backslashes in a published post | The escaping list is wrong for the current API version. Set `LINKEDIN_ESCAPE=0` and say so, so it can be fixed properly. |

That last one deserves a word. The versioned Posts API reads the post body as
"Little Text", where characters like `(` and `_` are markup. The tool escapes
them so they come out as themselves. If LinkedIn changes that list, escaping
becomes visible, and the switch is there to turn it off in the meantime.

## What this deliberately does not do

- **Scrape.** Reading other people's likers and commenters is not something
  LinkedIn's API offers, and the workarounds are against their terms.
- **Drive a browser.** That is the route that ends in a restricted account.
- **Post without you.** Every path here starts with you running a command.
