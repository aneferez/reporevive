from __future__ import annotations

from app.analyzers.testing_docs import assess_testing_docs

from .helpers import make_ctx

_GOOD_README = (
    "# Project\n\n" + "This project does things. " * 10 + "\n\n"
    "## Setup\n\nRun `npm install` and then `npm run dev` to start.\n"
)


def test_missing_tests_readme_deploy_all_flagged():
    ctx = make_ctx({"src/main.py": "print('hi')\n"})
    findings = assess_testing_docs(ctx)
    categories = {f.category for f in findings}
    assert "testing" in categories
    assert "documentation" in categories
    assert "deployment" in categories


def test_complete_project_has_no_testing_docs_findings():
    ctx = make_ctx(
        {
            "README.md": _GOOD_README,
            "tests/test_main.py": "def test_ok():\n    assert True\n",
            "Dockerfile": "FROM python:3.12\n",
            "src/main.py": "print('hi')\n",
        }
    )
    findings = assess_testing_docs(ctx)
    assert findings == []


def test_readme_without_setup_is_flagged():
    ctx = make_ctx(
        {
            "README.md": "# Project\n",
            "tests/test_main.py": "def test_ok():\n    assert True\n",
            "Dockerfile": "FROM python:3.12\n",
        }
    )
    findings = assess_testing_docs(ctx)
    assert any("setup instructions" in f.title for f in findings)
