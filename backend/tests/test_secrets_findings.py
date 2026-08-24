from __future__ import annotations

from app.analyzers.secrets import secret_findings
from app.security.redaction import SecretHit


def test_secret_findings_severity_and_masking():
    hits = [
        SecretHit(kind="private_key_block", line=1, masked_evidence="-----BEGIN PRIVATE KEY----- (redacted)", file="key.pem"),
        SecretHit(kind="aws_access_key_id", line=5, masked_evidence="AKIA… (redacted, 20 chars)", file="config.py"),
        SecretHit(kind="generic_secret_assignment", line=9, masked_evidence="s3cr… (redacted, 12 chars)", file="app.py"),
    ]
    findings = secret_findings(hits)
    by_file = {f.file: f for f in findings}

    assert by_file["key.pem"].severity.value == "critical"
    assert by_file["config.py"].severity.value == "high"
    assert by_file["app.py"].severity.value == "medium"

    # Generic assignment is lower-confidence and marked inferred.
    assert by_file["app.py"].verification_status.value == "inferred"
    assert by_file["config.py"].verification_status.value == "evidence_backed"

    # No raw secret leaks into the evidence.
    for f in findings:
        assert "redacted" in (f.evidence or "")


def test_secret_findings_deduplicated():
    hit = SecretHit(kind="github_token", line=3, masked_evidence="ghp_… (redacted)", file="a.py")
    findings = secret_findings([hit, hit])
    assert len(findings) == 1
