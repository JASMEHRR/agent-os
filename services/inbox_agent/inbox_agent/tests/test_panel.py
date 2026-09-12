"""Tests for the three agent panels.

A panel is a view, so what is worth protecting is that it stays one: that it
reports honestly when its agent is not connected, that edits go through the
domain rules rather than around them, and that nothing here re-decides
something the agent already decided.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from classroom_agent.coursework import Assignment, State
from classroom_agent.panel import ClassworkPanel
from classroom_agent.watcher import ClassroomWatcher
from inbox_agent.agent import Alert
from inbox_agent.panel import InboxPanel
from inbox_agent.triage import Importance
from opportunity_agent import Kind, Matcher, Opportunity, OpportunityTracker, Profile, make
from opportunity_agent.panel import ApplyPanel
from persistence.in_memory import InMemoryRepository

NOW = datetime(2026, 9, 12, 9, 0, tzinfo=UTC)


# ==================================================================== inbox


def inbox(*alerts: Alert) -> InboxPanel:
    store: InMemoryRepository[Alert] = InMemoryRepository()
    for alert in alerts:
        store.save(alert.message_id, alert)
    return InboxPanel(filters=InMemoryRepository(), alerts=store, setup="missing: EMAIL_PASSWORD")


def alert(subject: str = "Fee due", sent: bool = True, message_id: str = "<a@t>") -> Alert:
    return Alert(
        message_id,
        subject,
        "a@college.edu",
        Importance.IMPORTANT,
        "matters",
        NOW,
        NOW if sent else None,
        "" if sent else "quiet hours",
    )


def test_an_unconnected_mailbox_says_so_rather_than_looking_empty() -> None:
    state = inbox().state()
    assert state["configured"] is False
    assert "EMAIL_PASSWORD" in state["setup"]


def test_decisions_are_newest_first_and_counted() -> None:
    old = Alert("<old@t>", "Older", "a@b.edu", Importance.IMPORTANT, "", NOW - timedelta(hours=5), NOW)
    state = inbox(alert(), old).state()
    assert [a["subject"] for a in state["recent"]] == ["Fee due", "Older"]
    assert state["counts"] == {"decided": 2, "waiting": 0, "texted": 2}


def test_what_is_still_waiting_is_listed_separately() -> None:
    state = inbox(alert(sent=False)).state()
    assert state["counts"]["waiting"] == 1
    assert state["waiting"][0]["held_because"] == "quiet hours"


def test_a_filter_added_through_the_panel_is_stored_and_described() -> None:
    panel = inbox()
    made = panel.add_filter("never", "subject", "canteen")
    assert made["describes"] == "Never tell me about canteen"
    assert len(panel.state()["filters"]) == 1


def test_a_filter_that_could_never_fire_is_refused_by_the_panel_too() -> None:
    """Validation lives in the domain, so the panel cannot route around it."""
    with pytest.raises(ValueError, match="not an email address"):
        inbox().add_filter("never", "sender", "not-an-address")


def test_removing_a_filter_that_is_already_gone_is_not_an_error() -> None:
    panel = inbox()
    panel.remove_filter("nope")
    assert panel.state()["filters"] == []


def test_acting_without_a_connected_mailbox_explains_rather_than_crashes() -> None:
    with pytest.raises(RuntimeError, match="not connected"):
        inbox().check_now()
    with pytest.raises(RuntimeError, match="not connected"):
        inbox().send_digest()


# ==================================================================== apply


def apply_panel(*rows: Opportunity) -> ApplyPanel:
    store: InMemoryRepository[Opportunity] = InMemoryRepository()
    for row in rows:
        store.save(row.opportunity_id, row)
    return ApplyPanel(
        OpportunityTracker(
            sources=[],
            matcher=Matcher(Profile(graduation_year=2028)),
            store=store,
            reminders=InMemoryRepository(),
            now=lambda: NOW,
        )
    )


def listing(title: str = "Hackathon", days: int | None = 5) -> Opportunity:
    return make(
        title,
        "Org",
        f"https://x.test/{title}",
        Kind.HACKATHON,
        None if days is None else (NOW + timedelta(days=days)).date(),
    )


def test_open_rows_carry_what_the_card_needs() -> None:
    row = apply_panel(listing()).state()["open"][0]
    assert row["stage"] == "interested"
    assert row["days_left"] == 5
    assert row["closing_soon"] is True


def test_the_buttons_come_from_the_transition_table() -> None:
    row = apply_panel(listing()).state()["open"][0]
    assert "applied" in row["next_stages"]
    assert "won" not in row["next_stages"]


def test_missed_is_never_offered_as_a_button() -> None:
    """The scan sets it when a deadline passes. Nobody files their own failure."""
    row = apply_panel(listing()).state()["open"][0]
    assert "missed" not in row["next_stages"]


def test_moving_a_stage_goes_through_the_domain_machine() -> None:
    panel = apply_panel(listing())
    row = panel.state()["open"][0]
    moved = panel.move(row["id"], "applied")
    assert moved["stage"] == "applied"
    assert panel.state()["counts"]["applied"] == 1


def test_an_impossible_stage_move_is_refused_by_the_panel_too() -> None:
    panel = apply_panel(listing())
    row = panel.state()["open"][0]
    with pytest.raises(Exception, match="cannot go from interested to won"):
        panel.move(row["id"], "won")


def test_applying_takes_something_out_of_closing_this_week() -> None:
    panel = apply_panel(listing())
    assert len(panel.state()["closing"]) == 1
    panel.move(panel.state()["open"][0]["id"], "applied")
    assert panel.state()["closing"] == []


def test_adding_by_hand_parses_the_deadline() -> None:
    panel = apply_panel()
    added = panel.add("Flipkart GRiD", "Flipkart", "https://g.test", due="30 Sep 2026")
    assert added["deadline"] == "2026-09-30"
    assert len(panel.state()["open"]) == 1


def test_adding_something_with_no_title_is_refused() -> None:
    with pytest.raises(ValueError, match="needs a title"):
        apply_panel().add("   ", "Org", "https://x.test")


def test_an_undated_row_reports_no_days_left() -> None:
    row = apply_panel(listing(days=None)).state()["open"][0]
    assert row["days_left"] is None
    assert row["closing_soon"] is False


def test_a_scan_with_no_sources_reports_zeroes_rather_than_failing() -> None:
    assert apply_panel().scan()["found"] == 0


# ================================================================ classwork


class Source:
    def __init__(self, *items: Assignment) -> None:
        self.items = list(items)

    def assignments(self) -> list[Assignment]:
        return list(self.items)


def work(title: str = "Lab 3", hours: float = 5, state: State = State.NEW, wid: str = "a1") -> Assignment:
    return Assignment(wid, "c1", "Operating Systems", title, state, NOW + timedelta(hours=hours))


def classwork(*items: Assignment) -> ClassworkPanel:
    return ClassworkPanel(ClassroomWatcher(source=Source(*items), nudges=InMemoryRepository(), now=lambda: NOW))


def test_an_unconnected_classroom_says_how_to_connect() -> None:
    state = ClassworkPanel(setup="run --auth").state()
    assert state["configured"] is False
    assert "--auth" in state["setup"]
    assert state["outstanding"] == []


def test_outstanding_work_is_listed_and_counted() -> None:
    state = classwork(work(), work("Essay", hours=-5, wid="a2")).state()
    assert state["counts"] == {"outstanding": 2, "overdue": 1, "due_today": 1}
    assert any(a["overdue"] for a in state["outstanding"])


def test_turned_in_work_does_not_appear() -> None:
    assert classwork(work(state=State.TURNED_IN)).state()["counts"]["outstanding"] == 0


def test_a_classroom_outage_is_reported_on_the_tab_rather_than_raised() -> None:
    class Broken:
        def assignments(self) -> list[Assignment]:
            raise RuntimeError("HTTP 503")

    panel = ClassworkPanel(ClassroomWatcher(source=Broken(), nudges=InMemoryRepository()))
    state = panel.state()
    assert "503" in state["error"]
    assert state["outstanding"] == []


def test_check_now_refuses_politely_when_not_connected() -> None:
    with pytest.raises(RuntimeError, match="not connected"):
        ClassworkPanel().check_now()


def test_check_now_runs_the_watcher_when_connected() -> None:
    assert classwork(work()).check_now()["outstanding"] == 1
