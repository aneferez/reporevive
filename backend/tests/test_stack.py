from __future__ import annotations

from app.analyzers.stack import detect_stack

from .helpers import make_ctx


def test_detects_react_vite_fastapi_postgres_stack():
    ctx = make_ctx(
        {
            "frontend/package.json": (
                '{"dependencies":{"react":"18","react-dom":"18"},'
                '"devDependencies":{"vite":"5","typescript":"5","vitest":"1",'
                '"@testing-library/react":"14"}}'
            ),
            "frontend/tsconfig.json": "{}",
            "frontend/src/App.tsx": "export default function App(){ return null }",
            "backend/requirements.txt": "fastapi\nuvicorn\npsycopg2-binary\npytest\n",
            "backend/app/main.py": "from fastapi import FastAPI\napp = FastAPI()\n",
            ".env.example": "DATABASE_URL=postgres://localhost/db\n",
        }
    )
    result = detect_stack(ctx)
    assert result.stack.frontend == ["React", "Vite", "TypeScript"]
    assert "FastAPI" in result.stack.backend
    assert "Python" in result.stack.backend
    assert result.stack.database == ["PostgreSQL"]
    assert "Pytest" in result.stack.testing
    assert "Vitest" in result.stack.testing
    assert "React Testing Library" in result.stack.testing
    assert "pip" in result.package_managers


def test_invalid_package_json_produces_finding():
    ctx = make_ctx({"package.json": "{not valid json"})
    result = detect_stack(ctx)
    assert any(f.category == "dependency" and "package.json" in f.title.lower() for f in result.findings)


def test_no_stack_detected_is_empty():
    ctx = make_ctx({"notes.txt": "just some text\n"})
    result = detect_stack(ctx)
    assert result.stack.frontend == []
    assert result.stack.backend == []
