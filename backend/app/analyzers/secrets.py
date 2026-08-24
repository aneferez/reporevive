"""Secret-pattern findings (FR-07).

Turns the masked secret hits captured during intake redaction into findings.
Evidence is always masked; findings are described as *potential* exposures. The
raw secret value never appears here — only the masked sample from redaction.
"""

from __future__ import annotations

from ..models.enums import Category, Severity, VerificationStatus
from ..models.schemas import Finding
from ..security.redaction import SecretHit
from .base import make_finding

_KIND_LABELS = {
    "aws_access_key_id": "AWS access key id",
    "aws_secret_access_key": "AWS secret access key",
    "google_api_key": "Google API key",
    "github_token": "GitHub token",
    "github_pat": "GitHub personal access token",
    "slack_token": "Slack token",
    "stripe_secret_key": "Stripe secret key",
    "private_key_block": "private key",
    "json_web_token": "JSON Web Token",
    "generic_secret_assignment": "hardcoded credential",
}

# High-signal patterns are strong evidence; generic ones are lower confidence.
_HIGH_SIGNAL = {
    "aws_access_key_id", "aws_secret_access_key", "google_api_key",
    "github_token", "github_pat", "slack_token", "stripe_secret_key",
    "private_key_block",
}


def secret_findings(hits: list[SecretHit]) -> list[Finding]:
    # Deduplicate by (file, kind, line).
    seen: set[tuple[str | None, str, int]] = set()
    findings: list[Finding] = []
    for hit in hits:
        key = (hit.file, hit.kind, hit.line)
        if key in seen:
            continue
        seen.add(key)

        label = _KIND_LABELS.get(hit.kind, "credential")
        if hit.kind == "private_key_block":
            severity = Severity.critical
        elif hit.kind in _HIGH_SIGNAL:
            severity = Severity.high
        else:
            severity = Severity.medium

        high_signal = hit.kind in _HIGH_SIGNAL
        findings.append(
            make_finding(
                severity=severity,
                category=Category.secret,
                title=f"Potential exposed {label}",
                description=(
                    f"A value matching a {label} pattern was found in the source. "
                    "It has been masked in stored data. If this is a real secret it "
                    "must be treated as compromised."
                ),
                recommendation=(
                    "Remove the value from the repository, rotate the credential, and "
                    "load it from an environment variable or secret manager instead."
                ),
                file=hit.file,
                line=hit.line,
                evidence=hit.masked_evidence,
                confidence=0.85 if high_signal else 0.6,
                verification_status=(
                    VerificationStatus.evidence_backed
                    if high_signal
                    else VerificationStatus.inferred
                ),
            )
        )
    return findings
