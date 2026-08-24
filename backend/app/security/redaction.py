"""Secret-pattern detection and redaction (FR-07, PRD section 16).

Two responsibilities:

* ``redact_text`` masks suspected credentials so raw secrets are never stored,
  logged, sent to an AI provider, or returned to the client.
* It also returns the *hits* (kind + line + masked sample) so the phase-3 secret
  analyzer can turn them into masked, evidence-backed findings.

Findings derived from these hits must be described as *potential* exposures
unless independently confirmed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Placeholder inserted in stored text where a secret was removed.
REDACTION_MARK = "«redacted»"

# Values that are obviously not real secrets; skip to reduce false positives and
# avoid over-redacting example/template files.
_PLACEHOLDER_HINTS = (
    "replace",
    "your",
    "example",
    "changeme",
    "change_me",
    "changeit",
    "placeholder",
    "xxxx",
    "todo",
    "dummy",
    "sample",
    "localhost",
    "notreal",
    "fake",
    "<",
    ">",
    "...",
    "***",
    "redacted",
)


@dataclass
class SecretHit:
    kind: str
    line: int
    masked_evidence: str
    file: str | None = None


# (kind, pattern). Patterns with a named group ``secret`` redact only that group;
# others redact the whole match.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("aws_access_key_id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "aws_secret_access_key",
        re.compile(
            r"(?i)aws_secret_access_key\s*[=:]\s*['\"]?(?P<secret>[A-Za-z0-9/+=]{40})"
        ),
    ),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b")),
    ("google_oauth_token", re.compile(r"\bya29\.[A-Za-z0-9_\-]{20,}")),
    ("github_token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b")),
    ("github_pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("slack_webhook", re.compile(r"https://hooks\.slack\.com/services/[A-Za-z0-9/_+\-]{20,}")),
    ("stripe_secret_key", re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{16,}\b")),
    ("openai_api_key", re.compile(r"\bsk-[A-Za-z0-9]{32,}\b")),
    ("sendgrid_api_key", re.compile(r"\bSG\.[A-Za-z0-9_\-]{16,}\.[A-Za-z0-9_\-]{16,}\b")),
    (
        "azure_storage_key",
        re.compile(r"(?i)AccountKey\s*=\s*(?P<secret>[A-Za-z0-9+/=]{40,})"),
    ),
    (
        "json_web_token",
        re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    ),
    ("bearer_token", re.compile(r"(?i)\bbearer\s+(?P<secret>[A-Za-z0-9._\-]{20,})")),
    (
        # scheme://user:PASSWORD@host — redact the embedded password (>=8 chars).
        "connection_string_password",
        re.compile(r"://[^:/@\s]+:(?P<secret>[^@/\s]{8,})@"),
    ),
    (
        "generic_secret_assignment",
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret[_-]?key|secret|access[_-]?token"
            r"|refresh[_-]?token|auth[_-]?token|client[_-]?secret|token|password"
            r"|passwd|pwd|access[_-]?key|private[_-]?key|sas[_-]?token"
            r"|connection[_-]?string)\b\s*[=:]\s*"
            r"['\"](?P<secret>[^'\"\n]{6,})['\"]"
        ),
    ),
    (
        # Unquoted .env-style assignment of a sensitive key (>=12-char value).
        "env_secret_assignment",
        re.compile(
            r"(?i)(?:^|\b)[A-Za-z0-9_]*(?:api[_-]?key|secret|token|password|passwd"
            r"|access[_-]?key|private[_-]?key|client[_-]?secret|auth[_-]?token)"
            r"[A-Za-z0-9_]*\s*[=:]\s*(?P<secret>[A-Za-z0-9._\-+/=]{12,})"
        ),
    ),
]


def _looks_like_placeholder(value: str) -> bool:
    low = value.lower()
    if any(hint in low for hint in _PLACEHOLDER_HINTS):
        return True
    # A single repeated character or all-same is not a real secret.
    stripped = value.strip()
    return len(set(stripped)) <= 2


def mask_secret(value: str, kind: str) -> str:
    value = value.strip()
    if kind == "private_key_block":
        return "-----BEGIN PRIVATE KEY----- (redacted)"
    prefix = value[:4]
    return f"{prefix}… (redacted, {len(value)} chars)"


_PRIVATE_KEY_BEGIN = re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----")


def redact_text(text: str) -> tuple[str, list[SecretHit]]:
    """Return ``(redacted_text, hits)``. Line numbers are 1-based.

    Multi-line PEM private-key blocks are fully redacted (body included) while
    preserving the original line count, so downstream line references stay valid.
    """

    hits: list[SecretHit] = []
    out_lines: list[str] = []
    in_key_block = False

    for line_no, line in enumerate(text.splitlines(), start=1):
        if in_key_block:
            out_lines.append(REDACTION_MARK)
            if "PRIVATE KEY" in line.upper() and "END" in line.upper():
                in_key_block = False
            continue
        if _PRIVATE_KEY_BEGIN.search(line):
            hits.append(
                SecretHit(
                    kind="private_key_block",
                    line=line_no,
                    masked_evidence="-----BEGIN PRIVATE KEY----- (redacted)",
                )
            )
            # Stay in block unless END is on the same line (one-line block).
            in_key_block = "-----END" not in line.upper()
            out_lines.append(REDACTION_MARK)
            continue

        redacted = line
        for kind, pattern in _PATTERNS:

            def _replace(match: re.Match[str], _kind: str = kind) -> str:
                group = match.groupdict().get("secret")
                secret = group if group is not None else match.group(0)
                if _looks_like_placeholder(secret):
                    return match.group(0)
                hits.append(
                    SecretHit(
                        kind=_kind,
                        line=line_no,
                        masked_evidence=mask_secret(secret, _kind),
                    )
                )
                if group is not None:
                    return match.group(0).replace(secret, REDACTION_MARK)
                return REDACTION_MARK

            redacted = pattern.sub(_replace, redacted)
        out_lines.append(redacted)

    return "\n".join(out_lines), hits
