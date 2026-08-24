"""The content pipeline's domain: what you did, what it wrote, what you approved.

Deliberately small. Three records and one state machine, because the value of
this module is in the voice gates and the approval boundary, not in modelling
content management.

The state machine's shape carries the whole safety property: `PUBLISHED` is
reachable only from `APPROVED`, and only a human moves a draft into
`APPROVED`. There is no verb anywhere in this package that publishes an
unapproved draft, which is the same structural refusal the rest of the system
uses. Over a two-year unattended run, a check someone could bypass would
eventually be bypassed; a transition that does not exist cannot be.
"""

from __future__ import annotations

import dataclasses
import enum
from datetime import UTC, datetime


class DraftState(enum.Enum):
    """Where a post is in its life."""

    DRAFTED = "drafted"
    #: Failed the voice gates enough times that redrafting stopped. Kept
    #: rather than discarded: a repeated failure is information about the
    #: notes or the prompt, and deleting it hides that.
    REJECTED = "rejected"
    APPROVED = "approved"
    PUBLISHED = "published"
    #: Approved, then the publish failed. Distinct from DRAFTED because the
    #: human already said yes and should not be asked again.
    PUBLISH_FAILED = "publish_failed"
    DISCARDED = "discarded"


#: The only transitions that exist. PUBLISHED is unreachable except through
#: APPROVED, and nothing in this package moves a draft to APPROVED without a
#: named human principal.
TRANSITIONS: dict[DraftState, frozenset[DraftState]] = {
    DraftState.DRAFTED: frozenset({DraftState.APPROVED, DraftState.REJECTED, DraftState.DISCARDED}),
    DraftState.REJECTED: frozenset({DraftState.DRAFTED, DraftState.DISCARDED}),
    DraftState.APPROVED: frozenset({DraftState.PUBLISHED, DraftState.PUBLISH_FAILED, DraftState.DISCARDED}),
    DraftState.PUBLISH_FAILED: frozenset({DraftState.PUBLISHED, DraftState.DISCARDED}),
    DraftState.PUBLISHED: frozenset(),
    DraftState.DISCARDED: frozenset(),
}


class InvalidTransition(RuntimeError):
    """Attempted a state change the machine does not permit."""


class NotApproved(RuntimeError):
    """Attempted to publish something no human approved.

    Raised rather than returning False, because a caller ignoring a falsy
    return would publish, and the whole point of the boundary is that it
    cannot be walked past inattentively.
    """


@dataclasses.dataclass(frozen=True)
class WeeklyNote:
    """What actually happened, in your words.

    The single source of truth for every factual claim in a generated post.
    The model is instructed to use no number that is not here, and the voice
    gate that demands a concrete detail is what makes an empty note produce a
    visible failure rather than an invented achievement.
    """

    note_id: str
    captured_at: datetime
    body: str
    #: Optional steer. Empty means the agent picks the angle.
    angle: str = ""

    def is_substantive(self) -> bool:
        """Enough to write from.

        A one-line note produces a post with nothing in it, and the honest
        outcome is to say so rather than to generate filler.
        """
        return len(self.body.split()) >= 15


@dataclasses.dataclass(frozen=True)
class PostDraft:
    """One candidate post, and the record of how it got here."""

    draft_id: str
    note_id: str
    state: DraftState
    hook: str
    body: str
    close: str
    hashtags: tuple[str, ...]
    created_at: datetime
    #: How many times the voice gates sent it back. Worth keeping: a rising
    #: average across weeks means the prompt and the gates have drifted apart.
    redraft_count: int = 0
    #: Which rules failed on the final attempt, if it was rejected.
    outstanding: tuple[str, ...] = ()
    approved_by: str = ""
    approved_at: datetime | None = None
    published_at: datetime | None = None
    published_url: str = ""
    failure_reason: str = ""

    def full_text(self) -> str:
        """What would actually be posted."""
        tags = " ".join(t if t.startswith("#") else f"#{t}" for t in self.hashtags)
        return f"{self.hook}\n\n{self.body}\n\n{self.close}\n\n{tags}".strip()

    def transition_to(self, state: DraftState) -> PostDraft:
        if state not in TRANSITIONS[self.state]:
            raise InvalidTransition(f"{self.state.value} cannot become {state.value}")
        return dataclasses.replace(self, state=state)

    def approve(self, principal_id: str) -> PostDraft:
        """The human gate. No default, no timeout, no auto-approve.

        A `principal_id` is required rather than optional so an approval
        always names someone. An anonymous approval is indistinguishable from
        no approval, which is precisely the record this needs to not produce.
        """
        if not principal_id.strip():
            raise NotApproved("approval requires a named principal")
        return dataclasses.replace(
            self.transition_to(DraftState.APPROVED),
            approved_by=principal_id,
            approved_at=datetime.now(UTC),
        )

    def mark_published(self, url: str) -> PostDraft:
        if self.state is not DraftState.APPROVED and self.state is not DraftState.PUBLISH_FAILED:
            raise NotApproved(f"a draft in state {self.state.value} has no human approval to publish on")
        return dataclasses.replace(
            self.transition_to(DraftState.PUBLISHED),
            published_at=datetime.now(UTC),
            published_url=url,
        )

    def mark_publish_failed(self, reason: str) -> PostDraft:
        return dataclasses.replace(
            self.transition_to(DraftState.PUBLISH_FAILED),
            failure_reason=reason[:300],
        )
