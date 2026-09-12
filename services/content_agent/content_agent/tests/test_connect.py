"""Tests for the Connect screen.

Two things here can do real damage and both are tested hardest: writing the
file must never lose a line somebody else put there, and a secret must never
come back out of the panel it went into.
"""

from __future__ import annotations

import pathlib

import pytest

from content_agent.connect import GROUPS, ConnectPanel, read, write

ORIGINAL = """# Copy this file to .env and paste your keys in.
GROQ_API_KEY=gsk_existing

# Optional. A comment somebody wrote themselves.
REPOS=E:\\projects\\ventureadda
SOMETHING_ELSE=keep me
"""


@pytest.fixture
def env(tmp_path: pathlib.Path) -> pathlib.Path:
    path = tmp_path / ".env"
    path.write_text(ORIGINAL, encoding="utf-8")
    return path


# ================================================================== writing


def test_an_existing_key_is_replaced_in_place(env: pathlib.Path) -> None:
    write(env, {"GROQ_API_KEY": "gsk_new"})
    assert read(env)["GROQ_API_KEY"] == "gsk_new"
    assert env.read_text().index("GROQ_API_KEY") < env.read_text().index("REPOS")


def test_nothing_else_in_the_file_is_touched(env: pathlib.Path) -> None:
    """Rewriting from a template would silently delete somebody's own lines."""
    write(env, {"GROQ_API_KEY": "gsk_new"})
    after = env.read_text()
    assert "# Optional. A comment somebody wrote themselves." in after
    assert "SOMETHING_ELSE=keep me" in after
    assert "REPOS=E:\\projects\\ventureadda" in after


def test_a_new_key_is_appended_under_a_heading(env: pathlib.Path) -> None:
    write(env, {"WHATSAPP_TO": "+919876543210"})
    after = env.read_text()
    assert "# Added from the Connect screen." in after
    assert after.strip().endswith("WHATSAPP_TO=+919876543210")


def test_an_empty_value_removes_the_line_rather_than_blanking_it(env: pathlib.Path) -> None:
    """`KEY=` reads as "set to nothing", which is a different thing."""
    write(env, {"GROQ_API_KEY": ""})
    assert "GROQ_API_KEY" not in env.read_text()
    assert "GROQ_API_KEY" not in read(env)


def test_writing_to_a_file_that_does_not_exist_yet_creates_it(tmp_path: pathlib.Path) -> None:
    path = tmp_path / ".env"
    write(path, {"GROQ_API_KEY": "gsk_1"})
    assert read(path) == {"GROQ_API_KEY": "gsk_1"}


def test_several_keys_at_once(env: pathlib.Path) -> None:
    write(env, {"COLLEGE_EMAIL": "me@college.edu", "EMAIL_PASSWORD": "abcd efgh", "GROQ_API_KEY": "gsk_2"})
    stored = read(env)
    assert stored["COLLEGE_EMAIL"] == "me@college.edu"
    assert stored["EMAIL_PASSWORD"] == "abcd efgh"
    assert stored["GROQ_API_KEY"] == "gsk_2"


def test_a_key_this_screen_does_not_know_is_refused(env: pathlib.Path) -> None:
    """Otherwise the page becomes a way to write arbitrary environment."""
    with pytest.raises(ValueError, match="not a setting"):
        write(env, {"PATH": "/tmp/evil"})
    assert "PATH" not in env.read_text()


def test_a_line_break_in_a_value_is_refused(env: pathlib.Path) -> None:
    """One key per line, so a newline would silently become another setting."""
    with pytest.raises(ValueError, match="line break"):
        write(env, {"GROQ_API_KEY": "gsk_1\nSTUDIO_PASSWORD=letmein"})
    assert "STUDIO_PASSWORD" not in env.read_text()


def test_quotes_around_a_stored_value_are_stripped_on_read(tmp_path: pathlib.Path) -> None:
    path = tmp_path / ".env"
    path.write_text('GROQ_API_KEY="gsk_quoted"\n', encoding="utf-8")
    assert read(path)["GROQ_API_KEY"] == "gsk_quoted"


def test_an_empty_stored_value_does_not_count_as_set(tmp_path: pathlib.Path) -> None:
    path = tmp_path / ".env"
    path.write_text("GROQ_API_KEY=\n", encoding="utf-8")
    assert "GROQ_API_KEY" not in read(path)


# =================================================================== the panel


def test_a_secret_never_comes_back_out(env: pathlib.Path) -> None:
    """The one rule that turns every screenshot into a disclosure if broken."""
    state = ConnectPanel(env).state()
    fields = [f for g in state["groups"] for f in g["settings"]]
    secrets = [f for f in fields if f["secret"]]
    assert secrets, "there should be secret fields to check"
    assert all(f["value"] == "" for f in secrets)
    assert "gsk_existing" not in str(state)


def test_a_stored_secret_is_reported_as_set(env: pathlib.Path) -> None:
    state = ConnectPanel(env).state()
    groq = next(f for g in state["groups"] for f in g["settings"] if f["key"] == "GROQ_API_KEY")
    assert groq["set"] is True
    assert groq["value"] == ""


def test_a_non_secret_value_is_shown_so_it_can_be_edited(env: pathlib.Path) -> None:
    ConnectPanel(env).save({"COLLEGE_EMAIL": "me@college.edu"})
    state = ConnectPanel(env).state()
    field = next(f for g in state["groups"] for f in g["settings"] if f["key"] == "COLLEGE_EMAIL")
    assert field["value"] == "me@college.edu"


def test_a_group_is_connected_only_when_all_its_requirements_are_there(env: pathlib.Path) -> None:
    panel = ConnectPanel(env)
    mail = next(g for g in panel.state()["groups"] if g["id"] == "mail")
    assert mail["connected"] is False

    panel.save({"COLLEGE_EMAIL": "me@college.edu"})
    assert next(g for g in panel.state()["groups"] if g["id"] == "mail")["connected"] is False

    panel.save({"EMAIL_PASSWORD": "abcd"})
    assert next(g for g in panel.state()["groups"] if g["id"] == "mail")["connected"] is True


def test_saving_reports_what_it_wrote(env: pathlib.Path) -> None:
    panel = ConnectPanel(env)
    panel.save({"WHATSAPP_TO": "+91", "GRAD_YEAR": "2028"})
    assert panel.state()["saved"] == ["GRAD_YEAR", "WHATSAPP_TO"]


def test_the_panel_names_the_file_it_writes(env: pathlib.Path) -> None:
    state = ConnectPanel(env).state()
    assert state["path"] == str(env)
    assert state["exists"] is True


def test_values_are_trimmed_because_pasting_brings_whitespace(env: pathlib.Path) -> None:
    ConnectPanel(env).save({"GROQ_API_KEY": "  gsk_padded  "})
    assert read(env)["GROQ_API_KEY"] == "gsk_padded"


def test_every_group_requires_something_and_every_field_has_a_label() -> None:
    """A group with no requirements could never report itself connected."""
    for group in GROUPS:
        assert group.requires, f"{group.group_id} can never be connected"
        assert all(s.key in {x.key for x in group.settings} for s in group.settings)
        for setting in group.settings:
            assert setting.label, f"{setting.key} has no label"


def test_required_keys_actually_exist_among_the_groups_settings() -> None:
    """A typo in `requires` would make a group permanently unconnectable."""
    for group in GROUPS:
        keys = {s.key for s in group.settings}
        assert set(group.requires) <= keys, f"{group.group_id} requires a key it does not offer"
