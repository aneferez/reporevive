"""Deterministic repository analyzers (stack, config, API, secrets, tests/docs).

Added incrementally in phase 3. Each analyzer consumes redacted RepoFile
entries and emits evidence-backed findings; nothing here executes repo code.
"""
