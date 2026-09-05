"""Post to LinkedIn as yourself, through LinkedIn's own API.

Two jobs in one file:

* A **command line tool**. `auth` once to connect your account, then `post`
  whenever you want something published.
* A **custom poster** for the vendored linkedin-skills bundle. Those skills
  publish through Publora by default; setting `LINKEDIN_SKILLS_CUSTOM_POSTER`
  to this file makes them publish through your own LinkedIn app instead. The
  bundle hands us JSON on stdin and `<kind> <target_url>` as arguments, and
  reads back JSON on stdout.

WHY LINKEDIN'S OWN API RATHER THAN A SERVICE. Publishing to your own feed is
something LinkedIn supports directly and charges nothing for: register an app,
add the "Share on LinkedIn" and "Sign In with OpenID Connect" products, and you
hold a token that posts as you. A middleman costs money and holds the token on
your behalf. The route this file does NOT take is the third one: driving a
browser session. That is against LinkedIn's terms and reliably ends in a
restricted account, which is a bad trade for saving an afternoon of OAuth.

PUBLORA IS THE BACKUP, not the default. If the LinkedIn call cannot run
(no token yet, or it expired while you were asleep) and `PUBLORA_API_KEY` and
`PUBLORA_PLATFORM_ID` are set, the same text goes out through Publora instead.
That second variable is deliberately not the bundle's `LINKEDIN_PLATFORM_ID`:
setting the bundle's name makes the bundle route to Publora before this file is
ever called, and then "LinkedIn first" would be a comment rather than a fact.

Nothing here is imported by the studio. Post Studio still has no publish verb,
and this is a separate tool you run on purpose.
"""

from __future__ import annotations

import argparse
import dataclasses
import http.server
import json
import os
import pathlib
import secrets
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

REPO = pathlib.Path(__file__).resolve().parents[1]

AUTHORIZE_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"  # nosec B105 - an endpoint, not a credential
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
POSTS_URL = "https://api.linkedin.com/rest/posts"
SOCIAL_ACTIONS_URL = "https://api.linkedin.com/v2/socialActions"
PUBLORA_URL = "https://api.publora.com/api/v1/create-post"

#: `w_member_social` is the permission to post as you; `openid profile` is what
#: makes /v2/userinfo answer with your member id, which every post must name as
#: its author. Both come from self-serve products in the developer console.
SCOPES = "openid profile w_member_social"

#: The versioned APIs require this header, and LinkedIn retires versions on a
#: rolling schedule. Overridable precisely because a pinned date in a source
#: file ages: a 426 response means bump it, and the error message says so.
DEFAULT_API_VERSION = "202508"

#: LinkedIn truncates a post past this. Checked here so the failure is a
#: sentence rather than a 422 from an API.
MAX_POST_CHARS = 3000

#: The versioned Posts API parses `commentary` as "Little Text", where these
#: are markup rather than punctuation and have to be escaped to survive as
#: themselves. A post full of stray backslashes means this list is wrong for
#: the current version: set LINKEDIN_ESCAPE=0 and tell me.
RESERVED_CHARS = "\\|{}@[]()<>#*_~"

DEFAULT_REDIRECT = "http://localhost:8770/callback"
DEFAULT_TOKEN_PATH = REPO / ".linkedin.json"


class LinkedInError(RuntimeError):
    """An API call that failed, carrying enough to know what to do next."""

    def __init__(self, status: int, message: str, body: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.body = body


@dataclasses.dataclass(frozen=True)
class Credentials:
    """What `auth` earns and `post` spends."""

    access_token: str
    member_urn: str
    expires_at: str = ""

    def expired(self, now: datetime | None = None) -> bool:
        if not self.expires_at:
            return False
        moment = now or datetime.now(UTC)
        try:
            return datetime.fromisoformat(self.expires_at) <= moment
        except ValueError:
            return False

    def days_left(self, now: datetime | None = None) -> int | None:
        if not self.expires_at:
            return None
        try:
            when = datetime.fromisoformat(self.expires_at)
        except ValueError:
            return None
        return (when - (now or datetime.now(UTC))).days


# ------------------------------------------------------------------- Storage


def token_path() -> pathlib.Path:
    raw = os.environ.get("LINKEDIN_TOKEN_PATH", "").strip()
    return pathlib.Path(raw) if raw else DEFAULT_TOKEN_PATH


def load_credentials(path: pathlib.Path | None = None) -> Credentials | None:
    """The saved token, or None if `auth` has not been run here."""
    target = path or token_path()
    if not target.exists():
        return None
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    token = str(raw.get("access_token", ""))
    urn = str(raw.get("member_urn", ""))
    if not token or not urn:
        return None
    return Credentials(token, urn, str(raw.get("expires_at", "")))


def save_credentials(creds: Credentials, path: pathlib.Path | None = None) -> pathlib.Path:
    """Writes the token readable by nobody else.

    The permissions are set before the content is written, so the token is
    never briefly present in a world-readable file.
    """
    target = path or token_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.touch(mode=0o600, exist_ok=True)
    try:
        target.chmod(0o600)
    except OSError:
        # Windows does not implement POSIX modes. The file is still in a user
        # directory, and saying so is better than refusing to save.
        pass
    target.write_text(json.dumps(dataclasses.asdict(creds), indent=2), encoding="utf-8")
    return target


# ----------------------------------------------------------------- Transport


def _call(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """One HTTP call, with the error body kept rather than swallowed.

    urllib rather than requests, because the rest of this repository has no
    runtime dependencies and this did not need to be the exception.
    """
    request = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310 - fixed https hosts
            text = response.read().decode("utf-8")
            return dict(json.loads(text)) if text.strip() else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise LinkedInError(exc.code, _explain(exc.code, detail), detail) from None
    except urllib.error.URLError as exc:
        raise LinkedInError(0, f"could not reach {urllib.parse.urlsplit(url).netloc}: {exc.reason}") from None


def _explain(status: int, detail: str) -> str:
    """The status turned into the thing to actually do about it."""
    if status == 401:
        return "LinkedIn rejected the token. Run `python scripts/linkedin_post.py auth` again."
    if status == 403:
        return (
            "LinkedIn refused the request. The app is probably missing a product: "
            "add 'Share on LinkedIn' and 'Sign In with LinkedIn using OpenID Connect', "
            "then re-run auth so the new scopes are on the token."
        )
    if status == 426:
        return (
            f"The API version is too old. Set LINKEDIN_API_VERSION to a newer YYYYMM "
            f"(currently {api_version()}) and try again."
        )
    if status == 429:
        return "LinkedIn is rate limiting. Wait and try again."
    return f"LinkedIn returned {status}: {detail[:400]}"


def api_version() -> str:
    return os.environ.get("LINKEDIN_API_VERSION", "").strip() or DEFAULT_API_VERSION


def _api_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": api_version(),
    }


# --------------------------------------------------------------------- OAuth


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    """Catches the one redirect LinkedIn sends back."""

    query: dict[str, list[str]] = {}

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's naming
        _CallbackHandler.query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        done = "code" in _CallbackHandler.query
        message = "Connected. Close this tab and go back to the terminal." if done else "Something went wrong."
        page = f"<!doctype html><meta charset=utf-8><title>LinkedIn</title><p>{message}".encode()
        self.send_response(200 if done else 400)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(page)))
        self.end_headers()
        self.wfile.write(page)

    def log_message(self, format: str, *args: Any) -> None:
        return


def _await_redirect(
    redirect_uri: str,
    on_ready: Callable[[], None],
    timeout: float = 300.0,
) -> dict[str, list[str]]:
    """Listens for LinkedIn's one redirect and returns its query.

    `on_ready` runs once the listener is up, which is when the browser may
    safely be sent: opening it first would race the socket.
    """
    parts = urllib.parse.urlsplit(redirect_uri)
    _CallbackHandler.query = {}
    server = http.server.HTTPServer((parts.hostname or "localhost", parts.port or 80), _CallbackHandler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    try:
        on_ready()
        thread.join(timeout=timeout)
    finally:
        server.server_close()
    return _CallbackHandler.query


def authorize(
    client_id: str,
    client_secret: str,
    redirect_uri: str = DEFAULT_REDIRECT,
    *,
    open_browser: bool = True,
) -> Credentials:
    """The whole sign-in: open LinkedIn, catch the redirect, swap it for a token.

    The `state` is generated here and checked on the way back. Without that
    check any page could send your browser to the callback with a code of its
    choosing and connect your tool to somebody else's account.
    """
    state = secrets.token_urlsafe(24)
    query = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": SCOPES,
        }
    )
    url = f"{AUTHORIZE_URL}?{query}"

    def announce() -> None:
        print("\n  Opening LinkedIn in your browser. Approve the app there.")
        print(f"  If nothing opens, paste this:\n\n  {url}\n")
        if open_browser:
            webbrowser.open(url)

    answer = _await_redirect(redirect_uri, announce)
    if not answer:
        raise LinkedInError(0, "timed out waiting for LinkedIn to redirect back")
    if "error" in answer:
        raise LinkedInError(0, f"LinkedIn refused: {answer.get('error_description', answer['error'])[0]}")
    if answer.get("state", [""])[0] != state:
        raise LinkedInError(0, "the redirect carried the wrong state, so it was not the one we started")

    token = exchange_code(answer["code"][0], client_id, client_secret, redirect_uri)
    return dataclasses.replace(token, member_urn=fetch_member_urn(token.access_token))


def exchange_code(code: str, client_id: str, client_secret: str, redirect_uri: str) -> Credentials:
    """The authorization code, spent for an access token."""
    body = urllib.parse.urlencode(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        }
    ).encode()
    payload = _call(
        TOKEN_URL,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        body=body,
    )
    token = str(payload.get("access_token", ""))
    if not token:
        raise LinkedInError(0, "LinkedIn returned no access token")
    seconds = int(payload.get("expires_in", 0) or 0)
    expires = (datetime.now(UTC) + timedelta(seconds=seconds)).isoformat() if seconds else ""
    return Credentials(token, member_urn="", expires_at=expires)


def fetch_member_urn(token: str) -> str:
    """Who the token belongs to. Every post has to name its author."""
    payload = _call(USERINFO_URL, headers={"Authorization": f"Bearer {token}"})
    subject = str(payload.get("sub", ""))
    if not subject:
        raise LinkedInError(0, "LinkedIn did not say who this token belongs to (is 'profile' scope granted?)")
    return f"urn:li:person:{subject}"


# ------------------------------------------------------------------ Publishing


def escape_commentary(text: str) -> str:
    """Escapes what the Posts API treats as markup rather than punctuation.

    A bracket or an underscore left raw can be read as formatting and either
    vanish or take the rest of the line with it. Disable with LINKEDIN_ESCAPE=0
    if a published post ever comes out wearing backslashes.
    """
    if os.environ.get("LINKEDIN_ESCAPE", "1").strip() == "0":
        return text
    out = []
    for char in text:
        if char in RESERVED_CHARS:
            out.append("\\")
        out.append(char)
    return "".join(out)


def publish_post(creds: Credentials, text: str, *, visibility: str = "PUBLIC") -> dict[str, Any]:
    """A new post on your own feed."""
    if not text.strip():
        raise LinkedInError(0, "refusing to publish an empty post")
    if len(text) > MAX_POST_CHARS:
        raise LinkedInError(0, f"post is {len(text)} characters, LinkedIn takes {MAX_POST_CHARS}")

    body = {
        "author": creds.member_urn,
        "commentary": escape_commentary(text),
        "visibility": visibility,
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    request = urllib.request.Request(
        POSTS_URL,
        data=json.dumps(body).encode("utf-8"),
        headers=_api_headers(creds.access_token),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # nosec B310 - fixed https host
            # The id comes back in a header rather than the body, which is
            # empty on success.
            urn = response.headers.get("x-restli-id", "")
            return {"backend": "linkedin", "urn": urn, "url": _post_url(urn)}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise LinkedInError(exc.code, _explain(exc.code, detail), detail) from None
    except urllib.error.URLError as exc:
        raise LinkedInError(0, f"could not reach LinkedIn: {exc.reason}") from None


def _post_url(urn: str) -> str:
    identifier = urn.rsplit(":", 1)[-1] if urn else ""
    return f"https://www.linkedin.com/feed/update/{urn}/" if identifier else ""


def publish_comment(creds: Credentials, post_urn: str, text: str, parent: str = "") -> dict[str, Any]:
    """A comment on a post, or a reply when `parent` names a comment.

    Uses the social actions API rather than the versioned one, because that is
    the endpoint `w_member_social` covers for comments.
    """
    if not post_urn:
        raise LinkedInError(0, "no post to comment on")
    body: dict[str, Any] = {"actor": creds.member_urn, "message": {"text": text}}
    if parent:
        body["parentComment"] = parent
    quoted = urllib.parse.quote(post_urn, safe="")
    payload = _call(
        f"{SOCIAL_ACTIONS_URL}/{quoted}/comments",
        method="POST",
        headers=_api_headers(creds.access_token),
        body=json.dumps(body).encode("utf-8"),
    )
    return {"backend": "linkedin", "urn": str(payload.get("$URN", payload.get("id", "")))}


# ------------------------------------------------------------------- Fallback


def publora_configured() -> bool:
    return bool(os.environ.get("PUBLORA_API_KEY") and os.environ.get("PUBLORA_PLATFORM_ID"))


def publish_via_publora(text: str) -> dict[str, Any]:
    """The backup route, used only when LinkedIn's own could not run."""
    key = os.environ.get("PUBLORA_API_KEY", "")
    platform = os.environ.get("PUBLORA_PLATFORM_ID", "")
    payload = _call(
        PUBLORA_URL,
        method="POST",
        headers={"Content-Type": "application/json", "x-api-key": key},
        body=json.dumps({"content": text, "platforms": [platform]}).encode("utf-8"),
    )
    return {"backend": "publora", "response": payload}


def post_text(text: str, *, visibility: str = "PUBLIC") -> dict[str, Any]:
    """LinkedIn if it can, Publora if it cannot, an explanation if neither."""
    creds = load_credentials()
    if creds and not creds.expired():
        try:
            return publish_post(creds, text, visibility=visibility)
        except LinkedInError as exc:
            if not publora_configured():
                raise
            result = publish_via_publora(text)
            result["fell_back_from"] = str(exc)
            return result

    reason = "the saved token has expired" if creds else "no LinkedIn token is saved yet"
    if publora_configured():
        result = publish_via_publora(text)
        result["fell_back_from"] = reason
        return result
    raise LinkedInError(0, f"{reason}, and Publora is not configured either. Run `auth` first.")


# ------------------------------------------------------ The bundle's contract


def run_as_poster(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    """What linkedin-skills calls when LINKEDIN_SKILLS_CUSTOM_POSTER points here.

    The bundle passes the kind and the target on argv and the whole payload as
    JSON on stdin. A kind this cannot do is reported as such rather than
    silently doing something else: a reshare quietly published as a plain post
    would be worse than an error.
    """
    text = str(payload.get("draft_text", ""))
    if kind == "post":
        return post_text(text)

    if kind in ("comment", "reply"):
        creds = load_credentials()
        if not creds or creds.expired():
            raise LinkedInError(0, "no usable LinkedIn token. Run `auth` first.")
        parent = str(payload.get("parent_comment", "")) if kind == "reply" else ""
        return publish_comment(creds, str(payload.get("post_urn", "")), text, parent)

    raise LinkedInError(0, f"this poster does not do {kind!r}. Do it by hand, or use Publora for that one.")


# ----------------------------------------------------------------------- CLI


def _read_text(args: argparse.Namespace) -> str:
    if args.text:
        return str(args.text)
    if args.file:
        return pathlib.Path(args.file).read_text(encoding="utf-8")
    return sys.stdin.read()


def cmd_auth(args: argparse.Namespace) -> int:
    client_id = os.environ.get("LINKEDIN_CLIENT_ID", "").strip()
    client_secret = os.environ.get("LINKEDIN_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        print("\n  Set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET first.")
        print("  docs/LINKEDIN_POSTING.md walks through making the app.\n")
        return 1
    redirect = os.environ.get("LINKEDIN_REDIRECT_URI", "").strip() or DEFAULT_REDIRECT
    creds = authorize(client_id, client_secret, redirect, open_browser=not args.no_browser)
    where = save_credentials(creds)
    days = creds.days_left()
    print(f"\n  Connected as {creds.member_urn}")
    print(f"  Token saved to {where}" + (f", good for about {days} days.\n" if days is not None else ".\n"))
    return 0


def cmd_post(args: argparse.Namespace) -> int:
    text = _read_text(args)
    if args.dry_run:
        print(f"[dry run] {len(text)} characters, would go to LinkedIn as:\n")
        print(escape_commentary(text) if args.show_escaped else text)
        return 0
    result = post_text(text, visibility=args.visibility)
    if result.get("fell_back_from"):
        print(f"  LinkedIn could not take it ({result['fell_back_from']}), sent via Publora instead.")
    print(f"  Posted. {result.get('url') or result.get('urn') or ''}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    creds = load_credentials()
    print("\n  LinkedIn")
    if not creds:
        print("    no token saved. Run: python scripts/linkedin_post.py auth")
    elif creds.expired():
        print("    token EXPIRED. Run auth again.")
    else:
        days = creds.days_left()
        print(f"    ready, as {creds.member_urn}" + (f", about {days} days left" if days is not None else ""))
    print(f"    api version {api_version()}, token file {token_path()}")
    print("\n  Publora (backup)")
    print("    configured" if publora_configured() else "    not configured (optional)")
    print("\n  Skills bundle")
    wired = os.environ.get("LINKEDIN_SKILLS_CUSTOM_POSTER", "")
    print(f"    LINKEDIN_SKILLS_CUSTOM_POSTER={wired}" if wired else "    not wired up yet")
    if os.environ.get("LINKEDIN_PLATFORM_ID"):
        print("    warning: LINKEDIN_PLATFORM_ID is set, so the bundle will use Publora and skip this poster.")
    print()
    return 0


def cmd_poster(args: argparse.Namespace) -> int:
    """Invoked by the bundle: JSON on stdin, JSON on stdout."""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError as exc:
        print(json.dumps({"ok": False, "error": f"bad JSON on stdin: {exc}"}))
        return 2
    try:
        result = run_as_poster(args.kind, payload)
    except LinkedInError as exc:
        print(json.dumps({"ok": False, "error": str(exc), "status": exc.status}))
        return 1
    print(json.dumps({"ok": True, **result}))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="linkedin_post.py", description=__doc__.splitlines()[0])
    subs = parser.add_subparsers(dest="command")

    auth = subs.add_parser("auth", help="connect your LinkedIn account (do this once)")
    auth.add_argument("--no-browser", action="store_true", help="print the URL instead of opening it")
    auth.set_defaults(func=cmd_auth)

    post = subs.add_parser("post", help="publish text to your feed")
    post.add_argument("--text", help="the post itself")
    post.add_argument("--file", help="read the post from a file")
    post.add_argument("--visibility", default="PUBLIC", choices=("PUBLIC", "CONNECTIONS"))
    post.add_argument("--dry-run", action="store_true", help="show what would be sent, send nothing")
    post.add_argument("--show-escaped", action="store_true", help="with --dry-run, show the escaped form")
    post.set_defaults(func=cmd_post)

    check = subs.add_parser("check", help="say what is configured and what is missing")
    check.set_defaults(func=cmd_check)

    # Positional rather than a flag, because the bundle appends `<kind> <url>`
    # to whatever command it was given.
    poster = subs.add_parser("poster", help="internal: the linkedin-skills custom poster contract")
    poster.add_argument("kind")
    poster.add_argument("target_url", nargs="?", default="")
    poster.set_defaults(func=cmd_poster)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 1
    try:
        exit_code: int = args.func(args)
        return exit_code
    except LinkedInError as exc:
        print(f"\n  {exc}\n", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
