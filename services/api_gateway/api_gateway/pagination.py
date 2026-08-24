"""Cursor-based pagination (03 §32.6, 03 Rule 23).

03 §32.6 states the rule as **Non-Violable**: "No offset-based pagination
(`?page=2&limit=50`) in production APIs."

It is enforced structurally rather than by convention. `paginate` takes no
offset argument, so there is no code path that could serve one, and the
Gateway refuses a request carrying `page` or `offset` outright instead of
ignoring it. Silently ignoring the parameter would give the client a wrong
page and no indication of why.

The cursor encodes the last item's position opaquely. Clients that decode and
manipulate it get an unstable contract, which is the point: the cursor is the
server's bookmark, not an address the client computes.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, TypeVar

from core.exceptions import ValidationError

#: [Engineering Decision] 03 §32.6 shows `limit=50` in its example and names no
#: ceiling. 200 bounds a single response without constraining ordinary use.
DEFAULT_LIMIT = 50
MAX_LIMIT = 200

#: The query parameters that mean offset pagination. Their presence is refused.
OFFSET_PARAMETERS = ("page", "offset", "skip", "start")

T = TypeVar("T")


class OffsetPaginationRefused(ValidationError):
    """03 §32.6's Non-Violable Rule, enforced at the boundary."""


def encode_cursor(position: dict[str, Any]) -> str:
    raw = json.dumps(position, sort_keys=True, default=str).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(cursor: str) -> dict[str, Any]:
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        decoded = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
    except Exception as failure:
        raise ValidationError(f"cursor '{cursor}' is not a cursor this API issued") from failure
    if not isinstance(decoded, dict):
        raise ValidationError("a cursor must decode to an object")
    return decoded


@dataclass(frozen=True)
class Page:
    """One page plus the envelope of 03 §32.6."""

    data: list[Any]
    next_cursor: str | None
    prev_cursor: str | None
    limit: int
    total_count: int

    def to_body(self) -> dict[str, Any]:
        return {
            "data": list(self.data),
            "pagination": {
                "next_cursor": self.next_cursor,
                "prev_cursor": self.prev_cursor,
                "limit": self.limit,
                "total_count": self.total_count,
            },
        }


def assert_no_offset(query: dict[str, str]) -> None:
    """Refuse, rather than ignore, an offset-paginating request."""
    offending = [name for name in OFFSET_PARAMETERS if name in query]
    if offending:
        raise OffsetPaginationRefused(
            f"offset pagination is a Non-Violable Rule violation (03 §32.6); "
            f"remove {offending} and use `cursor` instead"
        )


def paginate(
    items: Sequence[Any],
    cursor: str | None = None,
    limit: int = DEFAULT_LIMIT,
    key: str = "id",
) -> Page:
    """Slices `items` forward from `cursor`. There is no offset parameter.

    The sequence is treated as already ordered by `key`; the cursor names the
    last item served, and the next page starts after it. Looking the position
    up by identity rather than by index is what keeps the page stable when
    items are inserted or removed between requests, which is the whole reason
    03 §32.6 forbids offsets.
    """
    if limit < 1:
        raise ValidationError("limit must be at least 1")
    limit = min(limit, MAX_LIMIT)

    start = 0
    if cursor is not None:
        position = decode_cursor(cursor)
        last_seen = position.get(key)
        start = len(items)
        for index, item in enumerate(items):
            if _key_of(item, key) == last_seen:
                start = index + 1
                break

    window = list(items[start : start + limit])
    next_cursor = None
    if start + limit < len(items) and window:
        next_cursor = encode_cursor({key: _key_of(window[-1], key)})
    prev_cursor = None
    if start > 0 and window:
        prev_cursor = encode_cursor({key: _key_of(items[max(0, start - limit)], key)})

    return Page(
        data=window,
        next_cursor=next_cursor,
        prev_cursor=prev_cursor,
        limit=limit,
        total_count=len(items),
    )


def _key_of(item: Any, key: str) -> Any:
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)
