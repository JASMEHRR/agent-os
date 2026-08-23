import pytest
from pydantic import ValidationError

from kernel.identity import ArtifactIdentity


def test_identity_shape_defaults():
    identity = ArtifactIdentity(artifact_type="decision", tenant_id="t1", created_by="agent-1")
    assert identity.artifact_id
    assert identity.trace_id
    assert identity.tenant_id == "t1"
    assert identity.artifact_type == "decision"


def test_identity_is_immutable():
    identity = ArtifactIdentity(artifact_type="decision", tenant_id="t1", created_by="agent-1")
    with pytest.raises(ValidationError):
        identity.tenant_id = "t2"
