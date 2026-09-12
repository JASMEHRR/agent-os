"""Tests for the Inbox Agent.

The behaviours worth protecting are the ones that make the difference between
an agent somebody keeps and one they mute in a week: never alerting twice,
never waking someone for something that can wait, never losing a held message,
and never letting a model outage stop the run.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from inbox_agent.agent import WATERMARK_ID, Alert, InboxAgent, Watermark
from inbox_agent.filters import FilterBook, new_filter
from inbox_agent.messages import Email
from inbox_agent.notify import Console, NotifyError
from inbox_agent.sources import BODY_CHARS, ImapSource, to_email
from inbox_agent.triage import IMPORTANT_AT, Importance, Triage
from persistence.in_memory import InMemoryRepository

ME = "jasmehr@college.edu"
NOON = datetime(2026, 9, 12, 12, 0, tzinfo=UTC)
NIGHT = datetime(2026, 9, 12, 2, 0, tzinfo=UTC)


def mail(
    subject: str,
    sender: str = "someone@college.edu",
    *,
    to: tuple[str, ...] = (ME,),
    bulk: bool = False,
    body: str = "",
    uid: str = "1",
    message_id: str = "",
) -> Email:
    return Email(
        message_id=message_id or f"<{subject[:20]}@test>",
        sender=sender,
        subject=subject,
        body=body,
        received_at=NOON,
        to=to,
        is_bulk=bulk,
        uid=uid,
    )


class FakeSource:
    """A mailbox that hands over whatever the test put in it."""

    def __init__(self, *emails: Email) -> None:
        self.emails = list(emails)
        self.asked_from: list[str] = []

    def fetch_since(self, last_uid: str, limit: int) -> list[Email]:
        self.asked_from.append(last_uid)
        return self.emails[:limit]


class Failing:
    """A notifier that never manages to send."""

    def send(self, text: str) -> None:
        raise NotifyError("the phone network is on fire")


def build(
    *emails: Email,
    notifier: object | None = None,
    now: datetime = NOON,
    **kwargs: object,
) -> tuple[InboxAgent, Console, FakeSource]:
    console = Console()
    source = FakeSource(*emails)
    agent = InboxAgent(
        source=source,
        triage=Triage(me=ME, vip_domains=frozenset({"college.edu"})),
        notifier=notifier or console,  # type: ignore[arg-type]
        alerts=InMemoryRepository(),
        watermarks=InMemoryRepository(),
        now=lambda: now,
        **kwargs,  # type: ignore[arg-type]
    )
    return agent, console, source


# ============================================================ triage: the rules


def test_a_placement_shortlist_is_urgent_without_asking_a_model() -> None:
    triage = Triage(me=ME, vip_domains=frozenset({"college.edu"}))
    verdict = triage.judge(mail("Shortlisted for the Deloitte interview - confirm by tomorrow"))
    assert verdict.importance is Importance.URGENT
    assert verdict.decided_by == "rules"


def test_a_newsletter_is_noise() -> None:
    triage = Triage(me=ME)
    verdict = triage.judge(mail("Weekly newsletter: campus happenings", to=(), bulk=True))
    assert verdict.importance is Importance.NOISE


def test_bulk_headers_outweigh_the_word_urgent() -> None:
    """Anyone can type "urgent"; only real bulk mail sets List-Unsubscribe."""
    triage = Triage(me=ME)
    shouty = triage.judge(mail("URGENT: webinar today, register now", to=(), bulk=True))
    assert shouty.importance is not Importance.URGENT


def test_fee_does_not_fire_on_coffee() -> None:
    triage = Triage(me=ME)
    assert not any(s.name == "money" for s in triage.signals_for(mail("Free coffee in the canteen")))


def test_a_muted_sender_is_silenced_whatever_they_write() -> None:
    triage = Triage(me=ME, muted_senders=frozenset({"spam@college.edu"}))
    verdict = triage.judge(mail("URGENT exam result deadline today", sender="spam@college.edu"))
    assert verdict.importance is Importance.NOISE


def test_being_named_as_a_recipient_counts_for_more_than_being_bcc_d() -> None:
    triage = Triage(me=ME)
    named = triage.score(mail("Project submission", to=(ME,)))[0]
    unnamed = triage.score(mail("Project submission", to=("someone.else@college.edu",)))[0]
    assert named > unnamed


def test_a_verdict_can_explain_itself() -> None:
    triage = Triage(me=ME)
    verdict = triage.judge(mail("Exam result published - check by tomorrow"))
    assert "assessment" in verdict.explain()


# ============================================================ triage: the model


def test_the_model_is_never_asked_when_the_rules_are_confident() -> None:
    asked: list[str] = []

    def classify(subject: str, sender: str, body: str) -> str:
        asked.append(subject)
        return "urgent"

    triage = Triage(me=ME, vip_domains=frozenset({"college.edu"}), classify=classify)
    triage.judge(mail("Shortlisted for the Deloitte interview - confirm by tomorrow"))
    triage.judge(mail("Newsletter: campus happenings", to=(), bulk=True))
    assert asked == []


def test_the_model_decides_only_the_unclear_middle() -> None:
    def classify(subject: str, sender: str, body: str) -> str:
        return "important"

    triage = Triage(me=ME, classify=classify)
    verdict = triage.judge(mail("Quick question about Thursday"))
    assert IMPORTANT_AT > verdict.score
    assert verdict.importance is Importance.IMPORTANT
    assert verdict.decided_by == "model"


def test_a_model_outage_degrades_to_routine_rather_than_stopping_the_run() -> None:
    def classify(subject: str, sender: str, body: str) -> str:
        raise RuntimeError("groq is down")

    triage = Triage(me=ME, classify=classify)
    verdict = triage.judge(mail("Quick question about Thursday"))
    assert verdict.importance is Importance.ROUTINE
    assert "unavailable" in verdict.reason


def test_an_unusable_model_answer_does_not_promote_the_message() -> None:
    triage = Triage(me=ME, classify=lambda s, f, b: "VERY SPICY")
    verdict = triage.judge(mail("Quick question about Thursday"))
    assert verdict.importance is Importance.ROUTINE


# ================================================================== the agent


def test_an_important_message_is_texted_and_recorded() -> None:
    agent, console, _ = build(mail("Exam result published - deadline tomorrow"))
    report = agent.run_once()
    assert report.alerted == 1
    assert len(console.sent) == 1
    assert "Exam result" in console.sent[0]


def test_the_same_message_is_never_alerted_twice() -> None:
    letter = mail("Fee payment due tomorrow")
    agent, console, source = build(letter)
    agent.run_once()
    # The mailbox hands it over again, as a mailbox will after a restart.
    source.emails = [letter]
    agent.watermarks.save(WATERMARK_ID, Watermark(last_uid=""))
    second = agent.run_once()
    assert second.alerted == 0
    assert len(console.sent) == 1


def test_noise_and_routine_never_buzz() -> None:
    agent, console, _ = build(
        mail("Newsletter: campus happenings", to=(), bulk=True, uid="1", message_id="<n@t>"),
        mail("Re: thanks", uid="2", message_id="<r@t>"),
    )
    report = agent.run_once()
    assert report.alerted == 0
    assert console.sent == []


def test_the_watermark_advances_so_the_next_run_starts_after_it() -> None:
    agent, _, source = build(
        mail("Fee due tomorrow", uid="7", message_id="<a@t>"),
        mail("Exam result out", uid="9", message_id="<b@t>"),
    )
    agent.run_once()
    assert agent.watermarks.get(WATERMARK_ID).last_uid == "9"
    source.emails = []
    agent.run_once()
    assert source.asked_from[-1] == "9"


# ------------------------------------------------------------- quiet hours


def test_important_mail_at_two_in_the_morning_is_held_not_sent() -> None:
    agent, console, _ = build(mail("Fee payment due"), now=NIGHT)
    report = agent.run_once()
    assert report.alerted == 0
    assert report.held == 1
    assert console.sent == []
    assert agent.pending()[0].held_because == "quiet hours"


def test_urgent_mail_still_wakes_you() -> None:
    agent, console, _ = build(mail("Shortlisted for the Deloitte interview - confirm by tomorrow"), now=NIGHT)
    report = agent.run_once()
    assert report.alerted == 1
    assert console.sent


def test_what_was_held_overnight_arrives_as_a_digest_in_the_morning() -> None:
    agent, console, source = build(mail("Fee payment due"), now=NIGHT)
    agent.run_once()
    assert console.sent == []

    agent.now = lambda: NOON
    source.emails = []
    report = agent.run_once()
    assert report.digest_sent
    assert "Fee payment due" in console.sent[0]
    assert agent.pending() == []


def test_a_quiet_window_that_wraps_midnight_is_understood() -> None:
    agent, _, _ = build()
    assert agent.in_quiet_hours(datetime(2026, 9, 12, 23, 30, tzinfo=UTC))
    assert agent.in_quiet_hours(datetime(2026, 9, 12, 3, 0, tzinfo=UTC))
    assert not agent.in_quiet_hours(datetime(2026, 9, 12, 12, 0, tzinfo=UTC))


def test_quiet_hours_can_be_turned_off_entirely() -> None:
    agent, _, _ = build(quiet_from=0, quiet_until=0)
    assert not agent.in_quiet_hours(NIGHT)


# -------------------------------------------------------------- rate limiting


def test_past_the_hourly_ceiling_the_agent_collects_instead_of_buzzing() -> None:
    letters = [mail(f"Fee payment due - instalment {n}", uid=str(n), message_id=f"<{n}@t>") for n in range(1, 7)]
    agent, console, _ = build(*letters, max_per_hour=2)
    report = agent.run_once()
    assert report.alerted == 2
    # The rest are held, then swept up by the digest in the same run.
    assert report.digest_sent
    assert len(console.sent) == 3


def test_a_held_message_is_delayed_never_dropped() -> None:
    agent, _, _ = build(mail("Fee payment due"), now=NIGHT)
    agent.run_once()
    assert len(agent.pending()) == 1


# ------------------------------------------------------------- failure paths


def test_a_send_failure_leaves_the_message_pending_rather_than_marked_sent() -> None:
    agent, _, _ = build(mail("Fee payment due"), notifier=Failing())
    report = agent.run_once()
    assert report.alerted == 0
    assert report.failures
    assert len(agent.pending()) == 1


def test_a_failed_digest_keeps_everything_pending() -> None:
    agent, _, _ = build(mail("Fee payment due"), notifier=Failing(), now=NIGHT)
    agent.run_once()
    agent.now = lambda: NOON
    assert agent.send_digest() is False
    assert len(agent.pending()) == 1


def test_a_digest_with_nothing_in_it_sends_nothing() -> None:
    agent, console, _ = build()
    assert agent.send_digest() is False
    assert console.sent == []


def test_a_long_digest_is_truncated_with_a_count() -> None:
    agent, console, _ = build()
    for n in range(15):
        agent.alerts.save(
            f"<{n}@t>",
            Alert(f"<{n}@t>", f"Subject {n}", "a@b.edu", Importance.IMPORTANT, "", NOON),
        )
    assert agent.send_digest(NOON)
    assert "and 3 more" in console.sent[0]


def test_old_sent_alerts_are_pruned_but_pending_ones_survive() -> None:
    agent, _, _ = build()
    long_ago = NOON - timedelta(days=40)
    agent.alerts.save("<old@t>", Alert("<old@t>", "Old", "a@b.edu", Importance.IMPORTANT, "", long_ago, long_ago))
    agent.alerts.save("<waiting@t>", Alert("<waiting@t>", "Waiting", "a@b.edu", Importance.IMPORTANT, "", long_ago))
    agent.run_once()
    ids = {a.message_id for a in agent.alerts.list_all()}
    assert "<old@t>" not in ids
    assert "<waiting@t>" in ids


# ==================================================================== parsing


RAW = b"""From: Placement Cell <placements@college.edu>
To: jasmehr@college.edu
Subject: Shortlisted for interview
Message-ID: <abc123@college.edu>
Date: Fri, 11 Sep 2026 09:30:00 +0530
Content-Type: text/plain; charset="utf-8"

You have been shortlisted. Report at 9am.
"""


def test_a_real_message_parses_into_the_fields_triage_reads() -> None:
    parsed = to_email(RAW, "42")
    assert parsed.sender == "placements@college.edu"
    assert parsed.sender_name == "Placement Cell"
    assert parsed.subject == "Shortlisted for interview"
    assert "shortlisted" in parsed.body.lower()
    assert parsed.addressed_to(ME)
    assert parsed.sender_domain == "college.edu"
    assert parsed.uid == "42"
    assert not parsed.is_bulk


def test_an_encoded_subject_is_decoded_so_the_keyword_rules_can_read_it() -> None:
    raw = b"Subject: =?UTF-8?B?RXhhbSByZXN1bHQgcHVibGlzaGVk?=\nFrom: a@b.edu\n\nbody\n"
    assert to_email(raw, "1").subject == "Exam result published"


def test_a_message_with_nothing_usable_in_it_still_parses() -> None:
    parsed = to_email(b"\r\n", "5")
    assert parsed.message_id == "uid:5"
    assert parsed.sender_domain == ""
    assert parsed.subject == ""


def test_an_unparseable_date_falls_back_to_now_rather_than_raising() -> None:
    parsed = to_email(b"Date: not a date\nFrom: a@b.edu\n\nbody\n", "1")
    assert parsed.received_at.tzinfo is not None


def test_html_only_mail_has_its_tags_stripped() -> None:
    raw = b'Content-Type: text/html; charset="utf-8"\nFrom: a@b.edu\n\n<p>Fee <b>due</b></p>\n'
    assert "Fee" in to_email(raw, "1").body
    assert "<p>" not in to_email(raw, "1").body


def test_a_body_is_truncated_before_it_can_leave_the_machine() -> None:
    raw = b"From: a@b.edu\nContent-Type: text/plain\n\n" + (b"secret " * 500)
    assert len(to_email(raw, "1").body) <= BODY_CHARS


def test_list_headers_mark_a_message_as_bulk() -> None:
    raw = b"From: a@b.edu\nList-Unsubscribe: <https://x/y>\nSubject: Hi\n\nbody\n"
    assert to_email(raw, "1").is_bulk


# ================================================================== notifiers


def test_callmebot_reports_a_refusal_rather_than_claiming_success(monkeypatch: pytest.MonkeyPatch) -> None:
    from inbox_agent import notify

    class Response:
        def read(self) -> bytes:
            return b"<html>ERROR: APIKey is not valid</html>"

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *exc: object) -> None:
            return None

    monkeypatch.setattr(notify.urllib.request, "urlopen", lambda *a, **k: Response())
    with pytest.raises(NotifyError, match="refused"):
        notify.CallMeBot(phone="+910000000000", apikey="wrong").send("hello")


def test_console_records_what_it_would_have_sent() -> None:
    console = Console()
    console.send("hello")
    assert console.sent == ["hello"]


# ==================================================================== filters


def test_a_never_rule_silences_mail_the_score_would_have_alerted_on() -> None:
    book = FilterBook([new_filter("never", "subject", "canteen")])
    triage = Triage(me=ME, vip_domains=frozenset({"college.edu"}), filters=book)
    verdict = triage.judge(mail("IMPORTANT: canteen menu and fee revision"))
    assert verdict.importance is Importance.NOISE
    assert verdict.decided_by == "filter"
    assert "canteen" in verdict.reason


def test_an_always_rule_alerts_on_mail_the_score_would_have_ignored() -> None:
    book = FilterBook([new_filter("always", "sender", "robotics@college.edu")])
    triage = Triage(me=ME, filters=book)
    verdict = triage.judge(mail("meetup on saturday", sender="robotics@college.edu", to=(), bulk=True))
    assert verdict.importance is Importance.IMPORTANT


def test_never_beats_always_when_both_match() -> None:
    """Silence is the recoverable mistake, so it wins the tie."""
    book = FilterBook([new_filter("always", "domain", "college.edu"), new_filter("never", "subject", "survey")])
    triage = Triage(me=ME, filters=book)
    assert triage.judge(mail("Student survey 2026")).importance is Importance.NOISE


def test_a_subject_filter_matches_whole_words_only() -> None:
    book = FilterBook([new_filter("never", "subject", "ai")])
    triage = Triage(me=ME, filters=book)
    assert triage.judge(mail("Please check your email settings")).importance is not Importance.NOISE
    assert triage.judge(mail("AI workshop on Friday")).importance is Importance.NOISE


def test_a_domain_filter_ignores_a_leading_at_sign() -> None:
    book = FilterBook([new_filter("never", "domain", "@spam.com")])
    assert book.decide(mail("Hi", sender="a@spam.com"))[0] is Importance.NOISE


def test_filters_that_match_nothing_leave_the_scoring_alone() -> None:
    book = FilterBook([new_filter("never", "subject", "quidditch")])
    triage = Triage(me=ME, vip_domains=frozenset({"college.edu"}), filters=book)
    assert triage.judge(mail("Exam result published")).importance is Importance.IMPORTANT


def test_a_filter_describes_itself_in_words() -> None:
    assert new_filter("never", "subject", "canteen").describe() == "Never tell me about canteen"
    assert new_filter("always", "domain", "college.edu").describe() == "Always tell me from anyone at college.edu"


@pytest.mark.parametrize(
    "rule,match,value,message",
    [
        ("never", "subject", "   ", "something to match"),
        ("sometimes", "subject", "x", "unknown filter"),
        ("never", "vibes", "x", "unknown filter"),
        ("never", "sender", "not-an-address", "not an email address"),
    ],
)
def test_a_filter_that_could_never_fire_is_refused_at_creation(rule: str, match: str, value: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        new_filter(rule, match, value)


# ============================================================== the IMAP fetch


class FakeImap:
    """Enough of imaplib to exercise the UID arithmetic, which is where the
    'never alert twice' guarantee actually lives."""

    def __init__(self, uids: list[str]) -> None:
        self.uids = uids
        self.selected: tuple[str, bool] | None = None
        self.searched: list[str] = []
        self.logged_out = False

    def login(self, user: str, password: str) -> None:
        return None

    def select(self, mailbox: str, readonly: bool = False) -> None:
        self.selected = (mailbox, readonly)

    def uid(self, command: str, *args: object) -> tuple[str, list[object]]:
        if command == "SEARCH":
            self.searched.append(str(args[-1]))
            # A real server answers `UID n:*` with the newest message even when
            # nothing is above n. Reproduced, because that is the quirk that
            # would otherwise re-alert the last message forever.
            return "OK", [" ".join(self.uids).encode()]
        wanted = str(args[0])
        raw = f"From: a@b.edu\nSubject: Message {wanted}\nMessage-ID: <{wanted}@b>\n\nbody\n".encode()
        return "OK", [(b"1 (RFC822 {" + str(len(raw)).encode() + b"}", raw)]

    def logout(self) -> None:
        self.logged_out = True


def imap_with(uids: list[str], monkeypatch: pytest.MonkeyPatch) -> tuple[ImapSource, FakeImap]:
    from inbox_agent import sources

    fake = FakeImap(uids)
    monkeypatch.setattr(sources.imaplib, "IMAP4_SSL", lambda host, port: fake)
    return ImapSource(host="imap.test", username="u", password="p"), fake


def test_the_mailbox_is_opened_read_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """An alerting agent has no business mutating the inbox it watches."""
    source, fake = imap_with(["1"], monkeypatch)
    source.fetch_since("", 10)
    assert fake.selected == ("INBOX", True)


def test_a_first_run_starts_at_uid_one(monkeypatch: pytest.MonkeyPatch) -> None:
    source, fake = imap_with(["1", "2"], monkeypatch)
    assert len(source.fetch_since("", 10)) == 2
    assert fake.searched == ["UID 1:*"]


def test_only_uids_above_the_watermark_come_back(monkeypatch: pytest.MonkeyPatch) -> None:
    source, _ = imap_with(["5", "6", "7"], monkeypatch)
    assert [e.uid for e in source.fetch_since("5", 10)] == ["6", "7"]


def test_the_servers_trailing_message_is_not_re_alerted(monkeypatch: pytest.MonkeyPatch) -> None:
    """`UID 9:*` answers with 9 when nothing is newer. It must yield nothing."""
    source, _ = imap_with(["9"], monkeypatch)
    assert source.fetch_since("9", 10) == []


def test_the_batch_limit_keeps_the_newest_not_the_oldest(monkeypatch: pytest.MonkeyPatch) -> None:
    source, _ = imap_with([str(n) for n in range(1, 51)], monkeypatch)
    assert [e.uid for e in source.fetch_since("", 3)] == ["48", "49", "50"]


def test_an_empty_mailbox_is_not_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    source, _ = imap_with([], monkeypatch)
    assert source.fetch_since("", 10) == []


def test_the_connection_is_closed_even_when_the_fetch_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    source, fake = imap_with(["1"], monkeypatch)
    monkeypatch.setattr(fake, "uid", lambda *a: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        source.fetch_since("", 10)
    assert fake.logged_out
