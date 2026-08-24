from __future__ import annotations

from app.security.redaction import REDACTION_MARK, redact_text


def test_redacts_aws_access_key():
    text = "const key = 'AKIA1234567890ABCDEF';\n"
    redacted, hits = redact_text(text)
    assert "AKIA1234567890ABCDEF" not in redacted
    assert REDACTION_MARK in redacted
    assert any(h.kind == "aws_access_key_id" for h in hits)
    assert hits[0].line == 1


def test_redacts_github_token():
    text = "TOKEN=ghp_abcdefghijklmnopqrstuvwxyz0123456789\n"
    redacted, hits = redact_text(text)
    assert "ghp_abcdefghijklmnopqrstuvwxyz0123456789" not in redacted
    assert any(h.kind == "github_token" for h in hits)


def test_redacts_generic_assignment_value_only():
    text = 'password = "s3cr3t-P@ssw0rd!"\n'
    redacted, hits = redact_text(text)
    assert "s3cr3t-P@ssw0rd!" not in redacted
    assert redacted.startswith("password = ")  # key kept, value masked
    assert any(h.kind == "generic_secret_assignment" for h in hits)


def test_placeholder_values_are_not_redacted():
    text = 'API_KEY = "your_api_key_here"\nGEMINI_API_KEY=replace_with_secret\n'
    redacted, hits = redact_text(text)
    assert redacted == text.rstrip("\n") or "your_api_key_here" in redacted
    assert hits == []


def test_masked_evidence_does_not_leak_secret():
    text = "aws_secret_access_key = 'abcdEFGH1234ijklMNOP5678qrstUVWX9012yzAB'\n"
    _redacted, hits = redact_text(text)
    assert hits, "expected an aws secret hit"
    for hit in hits:
        assert "abcdEFGH1234ijklMNOP5678qrstUVWX9012yzAB" not in hit.masked_evidence
        assert "redacted" in hit.masked_evidence
