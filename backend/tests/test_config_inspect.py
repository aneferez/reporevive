from __future__ import annotations

from app.analyzers.config_inspect import inspect_configuration

from .helpers import make_ctx


def test_missing_env_template_flagged():
    ctx = make_ctx(
        {
            "app.py": 'import os\nx = os.getenv("SECRET_TOKEN")\ny = os.environ["OTHER_VAR"]\n',
        }
    )
    findings = inspect_configuration(ctx)
    titles = [f.title for f in findings]
    assert any("Missing environment template" in t for t in titles)


def test_undocumented_env_var_flagged():
    ctx = make_ctx(
        {
            "app.py": 'import os\nx = os.getenv("SECRET_TOKEN")\ny = os.environ["OTHER_VAR"]\n',
            ".env.example": "SECRET_TOKEN=placeholder\n",
        }
    )
    findings = inspect_configuration(ctx)
    missing = [f for f in findings if "missing from .env.example" in f.title]
    assert missing
    assert "OTHER_VAR" in (missing[0].evidence or "")


def test_hardcoded_localhost_flagged():
    ctx = make_ctx({"src/client.ts": 'const base = "http://localhost:8000/api";\n'})
    findings = inspect_configuration(ctx)
    assert any("Hardcoded localhost" in f.title for f in findings)


def test_documented_env_produces_no_config_finding():
    ctx = make_ctx(
        {
            "app.py": 'import os\nx = os.getenv("SECRET_TOKEN")\n',
            ".env.example": "SECRET_TOKEN=placeholder\n",
        }
    )
    findings = inspect_configuration(ctx)
    assert not any(f.category == "configuration" for f in findings)
