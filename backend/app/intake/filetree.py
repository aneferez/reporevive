"""File filtering, path normalization, and text/binary classification.

Encodes the "commonly inspected" and "normally ignored" rules from PRD section
7. Path normalization is also a safety boundary: any entry that would escape the
archive root is rejected upstream.
"""

from __future__ import annotations

import posixpath

# Directory names ignored anywhere in the path (PRD section 7 + common noise).
IGNORED_DIRS = {
    "node_modules",
    "dist",
    "build",
    "coverage",
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "vendor",
    ".next",
    ".nuxt",
    ".cache",
    ".turbo",
    ".parcel-cache",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
    "site-packages",
}

# Extensions treated as inspectable text/source.
TEXT_EXTENSIONS = {
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".py", ".pyi",
    ".json", ".jsonc",
    ".toml", ".yaml", ".yml",
    ".md", ".markdown", ".mdx", ".rst",
    ".css", ".scss", ".sass", ".less",
    ".html", ".htm",
    ".txt",
    ".ini", ".cfg", ".conf",
    ".sh", ".bash", ".zsh",
    ".sql",
    ".vue", ".svelte", ".astro",
    ".graphql", ".gql",
    ".xml",
    ".env",
}

# Extensions that are definitely binary/generated; skip fast.
BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp", ".tiff", ".svg",
    ".pdf", ".zip", ".gz", ".tar", ".tgz", ".rar", ".7z", ".bz2",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".class", ".o", ".a",
    ".mp3", ".mp4", ".mov", ".avi", ".wav", ".ogg", ".webm",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".pyc", ".pyo", ".whl", ".egg",
    ".lock",  # lockfiles are large and low-signal for inspection
    ".map",   # source maps are generated
    ".db", ".sqlite", ".sqlite3",
}

# Filenames (no useful extension) that we always want to inspect.
SPECIAL_FILENAMES = {
    "dockerfile",
    "makefile",
    "procfile",
    "readme",
    "license",
    ".gitignore",
    ".dockerignore",
    ".editorconfig",
    "requirements.txt",
    "pipfile",
}


def normalize_path(raw: str) -> str | None:
    """Normalize an archive entry path to a safe, repo-relative POSIX path.

    Returns ``None`` if the entry is unsafe (absolute or escapes the root) — the
    caller treats that as an unsafe archive entry.
    """

    if not raw:
        return None
    path = raw.replace("\\", "/").strip()
    # Reject absolute paths and Windows drive/UNC forms.
    if path.startswith("/") or path.startswith("//") or (len(path) > 1 and path[1] == ":"):
        return None
    normalized = posixpath.normpath(path)
    if normalized in (".", ""):
        return None
    # After normalization any leading ".." means the entry escaped the root.
    if normalized == ".." or normalized.startswith("../"):
        return None
    return normalized


def is_ignored(path: str) -> bool:
    segments = path.split("/")
    if any(seg in IGNORED_DIRS for seg in segments):
        return True
    name = segments[-1].lower()
    if name.endswith(".min.js") or name.endswith(".min.css"):
        return True
    return False


def is_text_candidate(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    lower = name.lower()
    if lower in SPECIAL_FILENAMES:
        return True
    if lower.startswith(".env"):
        return True
    ext = _extension(lower)
    if ext in BINARY_EXTENSIONS:
        return False
    if ext in TEXT_EXTENSIONS:
        return True
    # Dotfiles like .babelrc / .prettierrc are usually JSON-ish config.
    if lower.startswith(".") and "rc" in lower:
        return True
    return False


def looks_binary(data: bytes) -> bool:
    """Heuristic: a NUL byte in the first chunk almost always means binary."""

    return b"\x00" in data[:8192]


def classify_language(path: str) -> str | None:
    ext = _extension(path.lower())
    mapping = {
        ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
        ".ts": "typescript", ".tsx": "typescript",
        ".py": "python", ".pyi": "python",
        ".json": "json", ".jsonc": "json",
        ".toml": "toml", ".yaml": "yaml", ".yml": "yaml",
        ".md": "markdown", ".markdown": "markdown", ".mdx": "markdown",
        ".css": "css", ".scss": "scss", ".sass": "sass", ".less": "less",
        ".html": "html", ".htm": "html",
        ".sql": "sql",
        ".sh": "shell", ".bash": "shell", ".zsh": "shell",
        ".vue": "vue", ".svelte": "svelte", ".astro": "astro",
    }
    if ext in mapping:
        return mapping[ext]
    name = path.rsplit("/", 1)[-1].lower()
    if name == "dockerfile":
        return "dockerfile"
    return None


def _extension(name: str) -> str:
    idx = name.rfind(".")
    return name[idx:] if idx > 0 else ""
