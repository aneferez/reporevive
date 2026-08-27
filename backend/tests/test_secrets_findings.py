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


def test_secret_findings_downweighted_in_fixture_paths():
    hits = [
        # Production path keeps its real severity.
        SecretHit(kind="aws_access_key_id", line=1, masked_evidence="AKIA… (redacted, 20 chars)", file="backend/config.py"),
        # Test / evaluation / mock / example paths -> informational.
        SecretHit(kind="aws_access_key_id", line=1, masked_evidence="AKIA… (redacted, 20 chars)", file="backend/tests/test_x.py"),
        SecretHit(kind="private_key_block", line=1, masked_evidence="-----BEGIN PRIVATE KEY----- (redacted)", file="backend/evaluation/samples.py"),
        SecretHit(kind="github_token", line=2, masked_evidence="ghp_… (redacted)", file="frontend/src/mockData.ts"),
        SecretHit(kind="stripe_secret_key", line=3, masked_evidence="sk_l… (redacted)", file=".env.example"),
    ]
    by_file = {f.file: f for f in secret_findings(hits)}

    assert by_file["backend/config.py"].severity.value == "high"
    for path in (
        "backend/tests/test_x.py",
        "backend/evaluation/samples.py",
        "frontend/src/mockData.ts",
        ".env.example",
    ):
        assert by_file[path].severity.value == "info", path
        assert by_file[path].confidence < 0.5, path
