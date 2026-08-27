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


def test_redacts_connection_string_password():
    secret = "Sup3rSecretDbPass"
    text = f"DATABASE_URL=postgresql://appuser:{secret}@db.example.com:5432/app\n"
    redacted, hits = redact_text(text)
    assert secret not in redacted
    assert any(h.kind == "connection_string_password" for h in hits)
    # Host and user survive; only the password is masked.
    assert "appuser" in redacted and "db.example.com" in redacted


def test_short_placeholder_db_password_not_redacted():
    # Common example creds (short) must not trip the connection-string pattern.
    text = "DATABASE_URL=postgres://user:pass@localhost/db\n"
    redacted, hits = redact_text(text)
    assert redacted.strip() == text.strip()
    assert hits == []


def test_redacts_bearer_token():
    text = "Authorization: Bearer abcDEF123456ghiJKL789mnoPQR\n"
    redacted, hits = redact_text(text)
    assert "abcDEF123456ghiJKL789mnoPQR" not in redacted
    assert any(h.kind == "bearer_token" for h in hits)


def test_redacts_openai_and_sendgrid_and_oauth():
    cases = [
        ("openai_api_key", "sk-" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6"),
        ("sendgrid_api_key", "SG.abcdefghij1234567890.abcdefghij1234567890XYZ"),
        ("google_oauth_token", "ya29.a0AeRealTokenMaterial1234567890XYZ"),
    ]
    for kind, secret in cases:
        redacted, hits = redact_text(f"const t = '{secret}';\n")
        assert secret not in redacted, kind
        assert any(h.kind == kind for h in hits), kind


def test_redacts_unquoted_env_secret():
    text = "API_SECRET=8f3a9b2c7d1e4f60a9b8c7d6e5f40312\n"
    redacted, hits = redact_text(text)
    assert "8f3a9b2c7d1e4f60a9b8c7d6e5f40312" not in redacted
    assert any(h.kind == "env_secret_assignment" for h in hits)


def test_env_secret_from_code_getenv_not_flagged():
    # Reading an env var in code is not a secret value.
    text = 'SECRET_TOKEN = os.getenv("SECRET_TOKEN")\n'
    _redacted, hits = redact_text(text)
    assert all(h.kind != "env_secret_assignment" for h in hits)


def test_redacts_real_private_key_block():
    # A genuine PEM block is still fully redacted and flagged.
    text = (
        "-----BEGIN PRIVATE KEY-----\n"
        "MIIBVAIBADANBgkqhkiG9w0BAQEFAASCAT4wggE6AgEAAkEA\n"
        "-----END PRIVATE KEY-----\n"
    )
    redacted, hits = redact_text(text)
    assert "MIIBVAIBADANBgkqhkiG9w0BAQEFAASCAT4wggE6AgEAAkEA" not in redacted
    assert any(h.kind == "private_key_block" for h in hits)


def test_private_key_marker_line_not_flagged():
    # A redaction/example marker (e.g. a redaction library's own mask string) is
    # not a real key exposure and must not be flagged.
    text = 'mask = "-----BEGIN PRIVATE KEY----- (redacted)"\n'
    redacted, hits = redact_text(text)
    assert all(h.kind != "private_key_block" for h in hits)
    assert redacted.strip() == text.strip()  # line kept as-is, not redacted


def test_code_references_not_flagged_as_secrets():
    # Ordinary source code with secret-shaped identifiers must not be flagged.
    for line in (
        "owner_token = new_owner_token()\n",
        "client = genai.Client(api_key=self.settings.gemini_api_key)\n",
        "token = _split_req_name(line)\n",
        "record.secret_hits = intake.secret_hits\n",
        "return { ownerToken: value.ownerToken };\n",
        "max_output_tokens=max_output_tokens\n",
    ):
        _redacted, hits = redact_text(line)
        assert hits == [], f"false positive on: {line!r} -> {[h.kind for h in hits]}"


def test_low_entropy_word_values_not_flagged():
    # A plain dictionary word (enum value, example placeholder) is not a secret.
    for line in ('secret = "secret"\n', "# scheme://user:PASSWORD@host redact it\n"):
        _redacted, hits = redact_text(line)
        assert hits == [], f"false positive on: {line!r} -> {[h.kind for h in hits]}"


def test_real_secret_next_to_code_still_flagged():
    # Precision changes must not suppress genuine secrets.
    _r, hits = redact_text('gemini_api_key = "AIzaSyA1234567890abcdefghijklmnopqrstuv"\n')
    assert any(h.kind in ("google_api_key", "generic_secret_assignment") for h in hits)
