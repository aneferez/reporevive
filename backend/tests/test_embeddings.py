from __future__ import annotations

from app.config import Settings
from app.retrieval.embeddings import EmbeddingIndex
from app.retrieval.factory import build_retriever
from app.retrieval.lexical import LexicalIndex

from .helpers import make_files


class FakeEmbedder:
    """Deterministic bag-of-keywords embedder for offline tests."""

    VOCAB = ["auth", "login", "widget", "render", "dashboard", "user", "order", "health"]

    def available(self) -> bool:
        return True

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(t.lower().count(w)) for w in self.VOCAB] for t in texts]


class UnavailableEmbedder:
    def available(self) -> bool:
        return False

    def embed(self, texts):
        raise RuntimeError("should not be called")


def test_embedding_index_ranks_by_similarity():
    files = make_files(
        {
            "src/widget.py": "def render_widget():\n    # renders the dashboard widget\n",
            "src/auth.py": "def login():\n    # user auth and login\n",
        }
    )
    idx = EmbeddingIndex.build(files, FakeEmbedder())
    hits = idx.search("widget render dashboard")
    assert hits
    assert hits[0].file == "src/widget.py"


def test_embedding_index_no_overlap_returns_empty():
    files = make_files({"src/widget.py": "render widget dashboard\n"})
    idx = EmbeddingIndex.build(files, FakeEmbedder())
    # 'zzzential' has no vocab overlap -> zero query vector -> no hits.
    assert idx.search("zzzential") == []


def test_factory_uses_embeddings_when_requested():
    r = build_retriever(
        make_files({"a.py": "widget render"}),
        Settings(retrieval_mode="embeddings"),
        embedder=FakeEmbedder(),
    )
    assert isinstance(r, EmbeddingIndex)


def test_factory_defaults_to_lexical():
    r = build_retriever(make_files({"a.py": "x = 1"}), Settings())
    assert isinstance(r, LexicalIndex)


def test_factory_falls_back_to_lexical_when_embedder_unavailable():
    r = build_retriever(
        make_files({"a.py": "x = 1"}),
        Settings(retrieval_mode="embeddings"),
        embedder=UnavailableEmbedder(),
    )
    assert isinstance(r, LexicalIndex)


def test_embeddings_retriever_powers_chat_interface():
    # The retriever is interchangeable: chat only relies on .search().
    files = make_files({"src/widget.py": "def render_widget():\n    # dashboard widget\n"})
    idx = EmbeddingIndex.build(files, FakeEmbedder())
    hits = idx.search("widget")
    assert hits and hits[0].excerpt()
