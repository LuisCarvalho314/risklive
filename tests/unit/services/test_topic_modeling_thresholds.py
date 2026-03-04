"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

from services.topic_modeling import modeling as topic_modeling_service


def test_modeling_dynamic_threshold_branches(monkeypatch):
    monkeypatch.setattr(topic_modeling_service, "_get_sentence_model", lambda *args, **kwargs: "s")
    monkeypatch.setattr(topic_modeling_service, "CountVectorizer", lambda **kwargs: "v")
    monkeypatch.setattr(topic_modeling_service, "UMAP", lambda **kwargs: "u")
    seen = []
    monkeypatch.setattr(topic_modeling_service, "HDBSCAN", lambda **kwargs: seen.append(kwargs) or "h")
    monkeypatch.setattr(topic_modeling_service, "BERTopic", lambda **kwargs: "t")
    cfg = topic_modeling_service.TopicModelConfig(
        hdbscan_min_cluster_size=None, hdbscan_min_samples=None
    )
    topic_modeling_service.initialize_models(150, cfg)
    topic_modeling_service.initialize_models(350, cfg)
    topic_modeling_service.initialize_models(450, cfg)
    assert seen[0]["min_cluster_size"] == 3 and seen[0]["min_samples"] == 3
    assert seen[1]["min_cluster_size"] == 6 and seen[1]["min_samples"] == 6
    assert seen[2]["min_cluster_size"] == 8 and seen[2]["min_samples"] == 8
