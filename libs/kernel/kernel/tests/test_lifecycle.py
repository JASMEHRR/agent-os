import pytest

from kernel.lifecycle import InvalidTransitionError, LifecycleStateMachine

TRANSITIONS = {
    "proposed": {"approved", "rejected"},
    "approved": {"executing"},
    "rejected": set(),
    "executing": {"completed", "failed"},
    "completed": set(),
    "failed": set(),
}


def test_allowed_transition_succeeds():
    sm = LifecycleStateMachine(transitions=TRANSITIONS, state="proposed")
    sm.transition("approved")
    assert sm.state == "approved"
    assert sm.history == ("proposed", "approved")


def test_disallowed_transition_rejected():
    sm = LifecycleStateMachine(transitions=TRANSITIONS, state="proposed")
    with pytest.raises(InvalidTransitionError):
        sm.transition("executing")
    assert sm.state == "proposed"


def test_terminal_state_has_no_transitions():
    sm = LifecycleStateMachine(transitions=TRANSITIONS, state="completed")
    assert not sm.can_transition("executing")
