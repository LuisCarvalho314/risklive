from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from models.csv import LLMEnrichedRow
from models.topic_model import TopicModelConfig
from services.topic_modeling import modeling as topic_service
from services.topic_modeling import visualization as topic_viz


def test_topic_modeling_basic(tmp_path, monkeypatch):
    from config import settings as settings_module

    monkeypatch.setattr(settings_module, "ROOT_DIR", tmp_path)
    settings_module._config = None

    rows = [
        LLMEnrichedRow(Title="A", RelevantKeywords=["alpha", "beta"], Timestamp="2024-01-01T00:00:00Z"),
        LLMEnrichedRow(Title="B", RelevantKeywords=["gamma", "delta"], Timestamp="2024-01-02T00:00:00Z"),
        LLMEnrichedRow(Title="C", RelevantKeywords=["alpha", "gamma"], Timestamp="2024-01-03T00:00:00Z"),
    ]
    config = TopicModelConfig(column_name="RelevantKeywords")

    dummy_topic_model = SimpleNamespace(
        topics_=[0, 1, 0],
        get_topics=lambda: {0: [("a", 1.0)], 1: [("b", 1.0)]},
        visualize_barchart=lambda topics=None: SimpleNamespace(to_json=lambda: "{}"),
        visualize_topics=lambda width=1000, height=1000: SimpleNamespace(to_json=lambda: "{}"),
        visualize_documents=lambda titles: SimpleNamespace(to_json=lambda: "{}"),
        topics_over_time=lambda docs, timestamps, topics=None, nr_bins=20: pd.DataFrame(),
        visualize_topics_over_time=lambda topics_over_time: SimpleNamespace(to_json=lambda: "{}"),
        hierarchical_topics=lambda docs: pd.DataFrame({"Parent_Name": [], "Parent_ID": [], "Topics": []}),
        get_topic_tree=lambda ht: "",
        save=lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(topic_service, "initialize_models", lambda *args, **kwargs: ("s", dummy_topic_model))
    monkeypatch.setattr(topic_service, "batch_generate_embeddings", lambda *args, **kwargs: [0, 1, 2])
    monkeypatch.setattr(topic_service, "train_topic_model", lambda *args, **kwargs: None)
    artifacts = topic_service.compute_topic_modeling(rows, config)
    assert artifacts.data_csv
    assert artifacts.visualizations.barchart_json is None


def test_generate_visualizations(tmp_path, monkeypatch):
    from config import settings as settings_module

    monkeypatch.setattr(settings_module, "ROOT_DIR", tmp_path)
    settings_module._config = None

    images_dir = tmp_path / "results" / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(
        [
            {
                "Title": "A",
                "RelevantKeywords": "alpha",
                "Timestamp": "2024-01-01T00:00:00Z",
                "AlertFlag": "Red",
                "topic": 0,
            },
            {
                "Title": "B",
                "RelevantKeywords": "beta",
                "Timestamp": "2024-01-02T00:00:00Z",
                "AlertFlag": "Yellow",
                "topic": 1,
            },
        ]
    )
    docs = ["alpha", "beta"]

    dummy_topic_model = SimpleNamespace(
        topics_=[0, 1],
        get_topics=lambda: {0: [("a", 1.0)], 1: [("b", 1.0)]},
        visualize_barchart=lambda topics=None: SimpleNamespace(to_json=lambda: "{}"),
        visualize_topics=lambda width=1000, height=1000: SimpleNamespace(to_json=lambda: "{}"),
        visualize_documents=lambda titles: SimpleNamespace(to_json=lambda: "{}"),
        topics_over_time=lambda docs, timestamps, topics=None, nr_bins=20: pd.DataFrame(),
        visualize_topics_over_time=lambda topics_over_time: SimpleNamespace(to_json=lambda: "{}"),
        hierarchical_topics=lambda docs: pd.DataFrame({"Parent_Name": [], "Parent_ID": [], "Topics": []}),
        get_topic_tree=lambda ht: "",
        save=lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(topic_viz, "create_two_treemaps", lambda data: SimpleNamespace())
    monkeypatch.setattr(topic_viz, "get_visualize_hierarchy", lambda *args, **kwargs: SimpleNamespace(to_json=lambda: "{}"))

    topic_viz.generate_visualizations(
        dummy_topic_model,
        docs,
        df,
        images_dir,
        TopicModelConfig(embedding_model_name="dummy"),
    )
