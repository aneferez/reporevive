"""Secret-pattern findings (FR-07).

Turns the masked secret hits captured during intake redaction into findings.
Evidence is always masked; findings are described as *potential* exposures. The
raw secret value never appears here — only the masked sample from redaction.
"""

from __future__ import annotations

from ..models.enums import Category, Severity, VerificationStatus
from ..models.schemas import Finding
from ..security.redaction import SecretHit
from .base import is_fixture_path, make_finding

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

# Secrets in test / fixture / sample / example paths are down-weighted to
# informational (see is_fixture_path in base) so a security tool's own fixtures —
# or any repo with example credentials — don't produce false "critical" findings.


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
        high_signal = hit.kind in _HIGH_SIGNAL
        if hit.kind == "private_key_block":
            severity = Severity.critical
        elif high_signal:
            severity = Severity.high
        else:
            severity = Severity.medium

        confidence = 0.85 if high_signal else 0.6
        verification = (
            VerificationStatus.evidence_backed if high_signal else VerificationStatus.inferred
        )
        description = (
            f"A value matching a {label} pattern was found in the source. "
            "It has been masked in stored data. If this is a real secret it "
            "must be treated as compromised."
        )
        recommendation = (
            "Remove the value from the repository, rotate the credential, and "
            "load it from an environment variable or secret manager instead."
        )

        if is_fixture_path(hit.file):
            # Almost certainly intentional test data — keep it visible but out of
            # the severity bars, readiness, and roadmap.
            severity = Severity.info
            confidence = 0.2
            verification = VerificationStatus.inferred
            description += (
                " This match is in a test, fixture, sample, or example path, so it "
                "is most likely intentional test data rather than a real exposure."
            )
            recommendation = (
                "Confirm this is intentional test data. If it is a real credential, "
                "remove it and rotate the secret; otherwise no action is needed."
            )

        findings.append(
            make_finding(
                severity=severity,
                category=Category.secret,
                title=f"Potential exposed {label}",
                description=description,
                recommendation=recommendation,
                file=hit.file,
                line=hit.line,
                evidence=hit.masked_evidence,
                confidence=confidence,
                verification_status=verification,
            )
        )
    return findings
