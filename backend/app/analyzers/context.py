"""Shared analysis context and lightweight parsing helpers.

Analyzers receive an ``AnalysisContext`` built from redacted ``RepoFile`` entries
and never touch the filesystem or execute anything. Parsing is best-effort and
defensive: malformed files return ``None`` rather than raising.
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass, field

from ..core.records import RepoFile


@dataclass
class AnalysisContext:
    files: list[RepoFile]
    by_path: dict[str, RepoFile] = field(default_factory=dict)

    @classmethod
    def build(cls, files: list[RepoFile]) -> "AnalysisContext":
        return cls(files=files, by_path={f.path: f for f in files})

    # --- lookups -----------------------------------------------------------
    def get(self, path: str) -> RepoFile | None:
        return self.by_path.get(path)

    def basename(self, path: str) -> str:
        return path.rsplit("/", 1)[-1]

    def find_by_name(self, name: str) -> list[RepoFile]:
        name = name.lower()
        return [f for f in self.files if self.basename(f.path).lower() == name]

    def first_by_name(self, name: str) -> RepoFile | None:
        matches = self.find_by_name(name)
        return matches[0] if matches else None

    def has_name(self, name: str) -> bool:
        return bool(self.find_by_name(name))

    def find_by_suffix(self, *suffixes: str) -> list[RepoFile]:
        return [f for f in self.files if f.path.lower().endswith(suffixes)]

    def find_by_language(self, *languages: str) -> list[RepoFile]:
        langs = set(languages)
        return [f for f in self.files if f.language in langs]

    def has_path_segment(self, segment: str) -> bool:
        seg = segment.lower()
        return any(seg in f.path.lower().split("/") for f in self.files)

    def name_matches(self, predicate) -> list[RepoFile]:
        return [f for f in self.files if predicate(self.basename(f.path).lower())]

    def search(
        self, pattern: str, *, languages: tuple[str, ...] | None = None, limit: int | None = None
    ) -> list[tuple[RepoFile, int, str]]:
        """Return ``(file, line_no, stripped_line)`` for each regex match."""

        rx = re.compile(pattern)
        langs = set(languages) if languages else None
        out: list[tuple[RepoFile, int, str]] = []
        for f in self.files:
            if langs is not None and f.language not in langs:
                continue
            for line_no, line in enumerate(f.content.splitlines(), start=1):
                if rx.search(line):
                    out.append((f, line_no, line.strip()))
                    if limit is not None and len(out) >= limit:
                        return out
        return out

    # --- parsed manifests --------------------------------------------------
    def package_jsons(self) -> list[tuple[str, dict]]:
        out: list[tuple[str, dict]] = []
        for f in self.find_by_name("package.json"):
            data = safe_json(f.content)
            if isinstance(data, dict):
                out.append((f.path, data))
        return out

    def all_npm_dependencies(self) -> dict[str, str]:
        deps: dict[str, str] = {}
        for _path, data in self.package_jsons():
            for key in ("dependencies", "devDependencies", "peerDependencies"):
                section = data.get(key)
                if isinstance(section, dict):
                    deps.update({k: str(v) for k, v in section.items()})
        return deps

    def requirements_text(self) -> str:
        parts = []
        for name in ("requirements.txt", "requirements-dev.txt"):
            for f in self.find_by_name(name):
                parts.append(f.content)
        return "\n".join(parts)

    def python_dependencies(self) -> set[str]:
        """Best-effort set of declared Python package names (lowercased)."""

        names: set[str] = set()
        for line in self.requirements_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            token = _split_req_name(line)
            if token:
                names.add(token.lower())
        for _path, data in self.pyproject_tomls():
            names.update(_pyproject_dep_names(data))
        return names

    def pyproject_tomls(self) -> list[tuple[str, dict]]:
        out: list[tuple[str, dict]] = []
        for f in self.find_by_name("pyproject.toml"):
            try:
                out.append((f.path, tomllib.loads(f.content)))
            except (tomllib.TOMLDecodeError, ValueError):
                continue
        return out


def safe_json(text: str) -> object | None:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


def _split_req_name(line: str) -> str | None:
    # Strip environment markers and extras/version specifiers.
    line = line.split(";", 1)[0].strip()
    for sep in ("==", ">=", "<=", "~=", "!=", ">", "<", "[", " ", "@"):
        idx = line.find(sep)
        if idx != -1:
            line = line[:idx]
    return line.strip() or None


def _pyproject_dep_names(data: dict) -> set[str]:
    names: set[str] = set()
    project = data.get("project", {})
    for dep in project.get("dependencies", []) or []:
        if isinstance(dep, str):
            token = _split_req_name(dep)
            if token:
                names.add(token.lower())
    # Poetry style.
    tool = data.get("tool", {})
    poetry = tool.get("poetry", {}) if isinstance(tool, dict) else {}
    for section in ("dependencies", "dev-dependencies"):
        deps = poetry.get(section, {})
        if isinstance(deps, dict):
            for name in deps:
                if name.lower() != "python":
                    names.add(name.lower())
    return names
