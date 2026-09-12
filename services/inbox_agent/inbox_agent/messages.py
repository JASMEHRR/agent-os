"""One received email, reduced to the parts triage actually reads.

Deliberately not an `email.message.Message`. That type is a live parser handle
over a MIME tree: it carries attachments, it is mutable, and it cannot be
stored. Triage needs a handful of fields and needs them frozen, because a
verdict that could change after it was recorded is a verdict nobody can audit.

Bodies arrive already decoded and already truncated. The truncation is a
privacy boundary rather than a performance one: a college inbox carries other
people's names, marks and medical notes, and the less of that leaves the
machine the better. See `sources.BODY_CHARS`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Email:
    """A received message. Immutable, storable, and free of MIME."""

    message_id: str
    sender: str
    subject: str
    body: str
    received_at: datetime
    sender_name: str = ""
    to: tuple[str, ...] = ()
    cc: tuple[str, ...] = ()
    #: True when the message carried `List-Id` or `List-Unsubscribe`. Bulk mail
    #: announces itself in the headers, which is a far better signal than
    #: guessing from the wording.
    is_bulk: bool = False
    in_reply_to: str = ""
    uid: str = ""

    @property
    def sender_domain(self) -> str:
        """Lowercased domain, or "" when the address is unparseable.

        Unparseable is not worth raising over. A malformed From: header is a
        property of some real mail, and triage should score it low rather than
        end the run.
        """
        _, _, domain = self.sender.partition("@")
        return domain.strip().strip(">").lower()

    def addressed_to(self, address: str) -> bool:
        """Whether `address` appears in To: or Cc:.

        A message that names you is likelier to want you than one that reached
        you through a list expansion, and this is the cheapest way to tell.
        """
        wanted = address.strip().lower()
        return any(wanted == a.strip().lower() for a in self.to + self.cc)
