from __future__ import annotations

from app.retrieval.lexical import LexicalIndex

from .helpers import make_files


def _index(files):
    return LexicalIndex.build(make_files(files))


def test_search_finds_relevant_file():
    idx = _index(
        {
            "src/auth.py": "def login(user):\n    return authenticate(user)\n",
            "src/widget.py": "def render_widget():\n    # renders the dashboard widget\n    pass\n",
        }
    )
    hits = idx.search("how does widget rendering work")
    assert hits
    assert hits[0].file == "src/widget.py"
    assert hits[0].start_line >= 1


def test_search_returns_empty_for_unknown_terms():
    idx = _index({"src/auth.py": "def login(user): return True\n"})
    assert idx.search("quokka platypus xylophone") == []


def test_empty_index_is_safe():
    idx = LexicalIndex.build([])
    assert idx.size == 0
    assert idx.search("anything") == []
