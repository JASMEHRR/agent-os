import dataclasses

import pytest

from kernel.journal import ImmutableJournal, JournalTamperError


def test_append_only_and_chained():
    journal = ImmutableJournal()
    e1 = journal.append({"event": "a"})
    e2 = journal.append({"event": "b"})
    assert e2.prev_hash == e1.entry_hash
    assert journal.verify_chain() is True


def test_entry_mutation_fails():
    journal = ImmutableJournal()
    entry = journal.append({"event": "a"})
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.payload = {"event": "tampered"}  # type: ignore[misc]


def test_tampered_chain_detected():
    journal = ImmutableJournal()
    journal.append({"event": "a"})
    journal.append({"event": "b"})
    # Simulate tampering by rewriting the underlying list with a modified payload.
    tampered_first = dataclasses.replace(journal[0], payload={"event": "TAMPERED"})
    journal._entries[0] = tampered_first
    with pytest.raises(JournalTamperError):
        journal.verify_chain()
