"""The loop: read what is new, judge it, and interrupt someone only if it earns it.

Four things stand between a verdict and a buzzing phone, and each exists
because of a specific way this kind of agent becomes unbearable.

**Never twice.** Every alert is recorded by `Message-ID` before it is sent. A
crash between sending and recording would re-alert, so the record is written
first: a duplicate silence is recoverable, a duplicate 3am buzz is not
forgiven.

**Not in the middle of the night.** `IMPORTANT` mail inside quiet hours is held
and delivered in the next morning's digest. `URGENT` still goes through — that
band exists precisely to name the mail worth waking someone for, and a quiet
hours rule that suppressed everything would make the distinction pointless.

**Not twenty at once.** Past an hourly ceiling the agent stops sending
individual alerts and starts collecting. Twenty buzzes in a minute is noise
that trains you to ignore the twenty-first, which will be the shortlist.

**Never silently.** A held or rate-limited message is not dropped. It waits in
the pending list until a digest carries it, so the failure mode is a late
alert rather than a lost one.

The agent sends without asking, which is the opposite of the posting agents in
this repository. A WhatsApp to your own number is a notification to the owner,
not a publication to five thousand strangers: nothing leaves your control, and
asking permission to tell you something would defeat the point. The Class A-D
approval boundary applies to effects on the world, and this has none.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from inbox_agent.messages import Email
from inbox_agent.notify import Notifier, NotifyError
from inbox_agent.sources import MailSource
from inbox_agent.triage import Importance, Triage, Verdict
from persistence.repository import NotFound, Repository

#: Where the watermark lives. One row, because there is one mailbox.
WATERMARK_ID = "watermark"

#: Alerts older than this stop being consulted for rate limiting and are
#: pruned, so the table does not grow without bound on a busy mailbox.
KEEP_ALERTS_FOR = timedelta(days=30)


@dataclass(frozen=True)
class Watermark:
    """The highest UID already considered. Not the highest alerted on."""

    last_uid: str = ""
    checked_at: datetime | None = None


@dataclass(frozen=True)
class Alert:
    """One message the agent decided about, and what it did."""

    message_id: str
    subject: str
    sender: str
    importance: Importance
    reason: str
    decided_at: datetime
    #: None while the message is still waiting for a digest.
    sent_at: datetime | None = None
    held_because: str = ""

    @property
    def pending(self) -> bool:
        return self.sent_at is None


@dataclass(frozen=True)
class RunReport:
    """What one poll did, for a log line and for the tests."""

    seen: int = 0
    alerted: int = 0
    held: int = 0
    routine: int = 0
    noise: int = 0
    digest_sent: bool = False
    failures: tuple[str, ...] = ()

    @property
    def quiet(self) -> bool:
        return self.alerted == 0 and not self.digest_sent


def _line(email: Email, verdict: Verdict) -> str:
    who = email.sender_name or email.sender
    mark = "!!" if verdict.importance is Importance.URGENT else "*"
    return f"{mark} {who}\n{email.subject}"


@dataclass
class InboxAgent:
    """Polls a mailbox and texts about what matters."""

    source: MailSource
    triage: Triage
    notifier: Notifier
    alerts: Repository[Alert]
    watermarks: Repository[Watermark]

    #: Local hours during which only URGENT gets through. Start is inclusive,
    #: end exclusive, and the window is allowed to wrap midnight.
    quiet_from: int = 23
    quiet_until: int = 7
    #: Individual alerts per rolling hour before the agent starts collecting.
    max_per_hour: int = 6
    #: Messages examined per poll. Bounds the first run against a full mailbox.
    batch: int = 25
    #: Injected so tests need no clock patching and quiet hours are testable.
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    # ---------------------------------------------------------------- helpers

    def _watermark(self) -> Watermark:
        try:
            return self.watermarks.get(WATERMARK_ID)
        except NotFound:
            return Watermark()

    def in_quiet_hours(self, when: datetime) -> bool:
        hour = when.astimezone().hour
        if self.quiet_from == self.quiet_until:
            return False
        if self.quiet_from < self.quiet_until:
            return self.quiet_from <= hour < self.quiet_until
        # Wraps midnight, which is the normal case for 23:00-07:00.
        return hour >= self.quiet_from or hour < self.quiet_until

    def _sent_last_hour(self, when: datetime) -> int:
        cutoff = when - timedelta(hours=1)
        return sum(1 for a in self.alerts.list_all() if a.sent_at is not None and a.sent_at >= cutoff)

    def pending(self) -> list[Alert]:
        """Everything judged worth telling him that has not been told yet."""
        return sorted((a for a in self.alerts.list_all() if a.pending), key=lambda a: a.decided_at)

    def _seen_before(self, message_id: str) -> bool:
        try:
            self.alerts.get(message_id)
        except NotFound:
            return False
        return True

    def _prune(self, when: datetime) -> None:
        cutoff = when - KEEP_ALERTS_FOR
        for alert in self.alerts.list_all():
            if not alert.pending and alert.sent_at is not None and alert.sent_at < cutoff:
                self.alerts.delete(alert.message_id)

    # -------------------------------------------------------------- the sends

    def _deliver(self, alert: Alert, text: str, when: datetime) -> str:
        """Sends, and records the outcome. Returns "" on success.

        The alert row already exists before this is called, so a crash mid-send
        leaves the message pending rather than forgotten or repeated.
        """
        try:
            self.notifier.send(text)
        except NotifyError as exc:
            return f"{alert.subject[:40]}: {exc}"
        self.alerts.save(alert.message_id, dataclasses.replace(alert, sent_at=when, held_because=""))
        return ""

    def send_digest(self, when: datetime | None = None) -> bool:
        """Sends everything pending as one message. True if anything went."""
        when = when or self.now()
        waiting = self.pending()
        if not waiting:
            return False

        head = f"{len(waiting)} from your inbox:" if len(waiting) > 1 else "From your inbox:"
        body = "\n\n".join(f"{a.importance.value.upper()} - {a.sender}\n{a.subject}" for a in waiting[:12])
        more = f"\n\n...and {len(waiting) - 12} more." if len(waiting) > 12 else ""
        try:
            self.notifier.send(f"{head}\n\n{body}{more}")
        except NotifyError:
            return False
        for alert in waiting:
            self.alerts.save(alert.message_id, dataclasses.replace(alert, sent_at=when, held_because=""))
        return True

    # ------------------------------------------------------------------ a run

    def run_once(self) -> RunReport:
        when = self.now()
        mark = self._watermark()
        fresh = self.source.fetch_since(mark.last_uid, self.batch)

        alerted = held = routine = noise = 0
        failures: list[str] = []
        highest = mark.last_uid

        for email in fresh:
            if email.uid.isdigit() and (not highest.isdigit() or int(email.uid) > int(highest)):
                highest = email.uid

            # Dedupe before judging: a message already decided about costs
            # nothing more, and must never be judged a second time.
            if self._seen_before(email.message_id):
                continue

            verdict = self.triage.judge(email)
            if verdict.importance is Importance.NOISE:
                noise += 1
                continue
            if verdict.importance is Importance.ROUTINE:
                routine += 1
                continue

            reason = ""
            if verdict.importance is Importance.IMPORTANT and self.in_quiet_hours(when):
                reason = "quiet hours"
            # `_sent_last_hour` already includes anything sent earlier in this
            # same run, because each alert is persisted as it goes out. Adding
            # the local counter on top double-counted and tripped the limiter
            # at half the configured ceiling.
            elif self._sent_last_hour(when) >= self.max_per_hour:
                reason = "too many already this hour"

            alert = Alert(
                message_id=email.message_id,
                subject=email.subject,
                sender=email.sender,
                importance=verdict.importance,
                reason=verdict.reason,
                decided_at=when,
                held_because=reason,
            )
            # Written before the send, deliberately. See the module docstring.
            self.alerts.save(alert.message_id, alert)

            if reason:
                held += 1
                continue

            failure = self._deliver(alert, _line(email, verdict), when)
            if failure:
                failures.append(failure)
                held += 1
            else:
                alerted += 1

        self.watermarks.save(WATERMARK_ID, Watermark(last_uid=highest, checked_at=when))
        self._prune(when)

        # Leaving quiet hours with things waiting is what makes held mail a
        # delay rather than a loss.
        digest = False
        if not self.in_quiet_hours(when) and self.pending():
            digest = self.send_digest(when)

        return RunReport(len(fresh), alerted, held, routine, noise, digest, tuple(failures))
