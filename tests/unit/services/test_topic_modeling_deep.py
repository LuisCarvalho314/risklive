"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from models.csv import LLMEnrichedRow
from models.topic_model import TopicModelConfig
from services.topic_modeling import modeling as tm


def test_normalize_keywords_variants():
    assert tm._normalize_keywords(None) == ""
    assert tm._normalize_keywords(["a", "b"]) == "a, b"
    assert tm._normalize_keywords("['a','b']") == "a, b"
    assert tm._normalize_keywords("[a,b") == "a, b"
    assert tm._normalize_keywords("plain") == "plain"
    assert tm._normalize_keywords(123) == "123"


def test_get_sentence_model_cache(monkeypatch):
    calls = {"count": 0}

    class DummySentenceModel:
        def __init__(self, name):
            calls["count"] += 1
            self.name = name

    monkeypatch.setattr(tm, "SentenceTransformer", DummySentenceModel)
    tm._SENTENCE_MODEL_CACHE.clear()
    first = tm._get_sentence_model("m", cache=True)
    second = tm._get_sentence_model("m", cache=True)
    assert first is second
    assert calls["count"] == 1


def test_prepare_dataframe_missing_column_raises():
    rows = [LLMEnrichedRow(Title="A", RelevantKeywords=["x"])]
    with pytest.raises(ValueError):
        tm._prepare_dataframe(rows, "MissingCol")


def test_initialize_models_dynamic_branch(monkeypatch):
    monkeypatch.setattr(tm, "_get_sentence_model", lambda *args, **kwargs: "sentence")
    monkeypatch.setattr(tm, "CountVectorizer", lambda stop_words=None: ("vec", stop_words))
    monkeypatch.setattr(tm, "UMAP", lambda **kwargs: ("umap", kwargs))
    monkeypatch.setattr(tm, "HDBSCAN", lambda **kwargs: ("hdbscan", kwargs))
    monkeypatch.setattr(tm, "BERTopic", lambda **kwargs: ("topic", kwargs))

    config = TopicModelConfig(hdbscan_min_cluster_size=None, hdbscan_min_samples=None)
    sentence_model, topic_model = tm.initialize_models(50, config)
    assert sentence_model == "sentence"
    assert topic_model[0] == "topic"

    cfg_static = TopicModelConfig(hdbscan_min_cluster_size=9, hdbscan_min_samples=4)
    sentence_model2, topic_model2 = tm.initialize_models(500, cfg_static)
    assert sentence_model2 == "sentence"
    assert topic_model2[0] == "topic"


def test_metadata_roundtrip(tmp_path):
    meta = {"config": TopicModelConfig().model_dump()}
    tm._save_metadata(tmp_path, meta)
    loaded = tm._load_config_from_metadata(tmp_path)
    assert loaded is not None
    assert isinstance(loaded, TopicModelConfig)

    (tmp_path / "run_metadata.json").write_text("not-json")
    assert tm._load_config_from_metadata(tmp_path) is None
    (tmp_path / "run_metadata.json").write_text('{"x":1}')
    assert tm._load_config_from_metadata(tmp_path) is None


def test_save_core_artifacts(tmp_path, monkeypatch):
    images = tmp_path / "images"
    data = tmp_path / "data"
    model = tmp_path / "models"
    monkeypatch.setattr(tm, "_resolve_save_dirs", lambda: (images, data, model))

    class DummyTopicModel:
        def save(self, *args, **kwargs):
            return None

    df = pd.DataFrame([{"Title": "A", "RelevantKeywords": "x", "topic": 1}])
    img, data_dir, model_dir = tm.save_core_artifacts(DummyTopicModel(), df, TopicModelConfig())
    assert img.exists()
    assert (data_dir / "df_with_response_and_topics.csv").exists()
    assert model_dir.exists()


def test_compute_topic_modeling_no_documents():
    rows = [LLMEnrichedRow(Title="A", RelevantKeywords="", Timestamp="2024-01-01T00:00:00Z")]
    with pytest.raises(ValueError):
        tm.compute_topic_modeling(rows, TopicModelConfig(column_name="RelevantKeywords"))


def test_compute_topic_modeling_success(monkeypatch):
    rows = [
        LLMEnrichedRow(Title="A", RelevantKeywords=["alpha"], Timestamp="2024-01-01T00:00:00Z"),
        LLMEnrichedRow(Title="B", RelevantKeywords=["beta"], Timestamp="2024-01-02T00:00:00Z"),
    ]

    dummy_topic_model = SimpleNamespace(topics_=[0, 1])
    monkeypatch.setattr(tm, "initialize_models", lambda *args, **kwargs: ("sentence", dummy_topic_model))
    monkeypatch.setattr(tm, "batch_generate_embeddings", lambda *args, **kwargs: [0, 1])
    monkeypatch.setattr(tm, "train_topic_model", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        tm,
        "save_core_artifacts",
        lambda *args, **kwargs: (Path("images"), Path("data"), Path("model")),
    )
    monkeypatch.setattr(tm, "_save_metadata", lambda *args, **kwargs: "ok")
    artifacts = tm.compute_topic_modeling(rows, TopicModelConfig(column_name="RelevantKeywords"))
    assert artifacts.assignments


def test_batch_generate_embeddings_and_train():
    class DummySentenceModel:
        def encode(self, docs, **kwargs):
            assert kwargs.get("show_progress_bar") is False
            assert kwargs.get("batch_size") == 8
            return [1, 2]

    class DummyTopicModel:
        def __init__(self):
            self.called = False

        def fit(self, docs, embeddings):
            self.called = True
            assert docs == ["a"]
            assert embeddings == [1]

    embeddings = tm.batch_generate_embeddings(
        DummySentenceModel(),
        ["a", "b"],
        TopicModelConfig(embedding_batch_size=8, embedding_show_progress=False),
    )
    assert embeddings == [1, 2]
    topic_model = DummyTopicModel()
    tm.train_topic_model(topic_model, ["a"], [1])
    assert topic_model.called is True
