from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from services.topic_modeling import visualization as tv


def _dummy_topic_model():
    return SimpleNamespace(
        get_topic_freq=lambda: pd.DataFrame({"Topic": [0, 1], "Count": [1, 1]}),
        get_topics=lambda: {0: [("a", 1.0)], 1: [("b", 1.0)]},
        get_topic=lambda topic: [("kw", 1.0)],
        c_tf_idf_=None,
        topic_embeddings_=[[1.0, 0.0], [0.0, 1.0]],
        topic_aspects_={"custom": {0: [("ax", 1.0)], 1: [("bx", 1.0)]}},
        custom_labels_=None,
        _outliers=0,
    )


def test_get_visualize_hierarchy_and_annotations(monkeypatch):
    class DummyFig:
        def __init__(self, n_topics: int):
            ticks = list(range(n_topics))
            self.layout = {"yaxis": {"ticktext": ticks}, "xaxis": {"ticktext": ticks}}
            self.data = [
                {"x": np.array([1, 2, 3, 4]), "y": np.array([1, 2, 3, 4]), "text": ["a", "b", "c", "d"]}
            ]

        def update_layout(self, **kwargs):
            return self

        def add_trace(self, *_args, **_kwargs):
            return None

        def __getitem__(self, key):
            if key == "data":
                return self.data
            raise KeyError(key)

    monkeypatch.setattr(tv.ff, "create_dendrogram", lambda embeddings, *args, **kwargs: DummyFig(int(embeddings.shape[0])))
    monkeypatch.setattr(tv, "validate_distance_matrix", lambda x, n: x)

    topic_model = _dummy_topic_model()
    fig = tv.get_visualize_hierarchy(topic_model, orientation="left", width=400, height=300)
    assert fig is not None
    fig2 = tv.get_visualize_hierarchy(topic_model, top_n_topics=1, orientation="bottom", width=400, height=300)
    assert fig2 is not None

    topic_model.custom_labels_ = ["c0", "c1"]
    fig3 = tv.get_visualize_hierarchy(topic_model, topics=[0, 1], custom_labels=True, orientation="bottom", width=400, height=300)
    assert fig3 is not None
    fig4 = tv.get_visualize_hierarchy(topic_model, topics=[0, 1], custom_labels="custom", orientation="bottom", width=400, height=300)
    assert fig4 is not None

    monkeypatch.setattr(tv.sch, "dendrogram", lambda *args, **kwargs: {"leaves": [0, 1], "icoord": [[5, 6, 15, 16]]})
    out = tv._get_annotations(
        topic_model=topic_model,
        hierarchical_topics=pd.DataFrame({"Parent_Name": [], "Parent_ID": [], "Topics": []}),
        embeddings=np.array([[1.0, 0.0], [0.0, 1.0]]),
        linkage_function=lambda x: np.array([[0, 1, 0.5, 2]]),
        distance_function=lambda x: np.array([[0.0, 0.1], [0.1, 0.0]]),
        orientation="left",
    )
    assert isinstance(out, list)
    out2 = tv._get_annotations(
        topic_model=topic_model,
        hierarchical_topics=pd.DataFrame({"Parent_Name": ["P"], "Parent_ID": [99], "Topics": [[0, 1]]}),
        embeddings=np.array([[1.0, 0.0], [0.0, 1.0]]),
        linkage_function=lambda x: np.array([[0, 1, 0.5, 2]]),
        distance_function=lambda x: np.array([[0.0, 0.1], [0.1, 0.0]]),
        orientation="left",
        custom_labels="custom",
    )
    assert isinstance(out2, list)


def test_visualization_helpers_and_compute_paths(tmp_path, monkeypatch):
    ts = tv.parse_timestamp("2024-01-01T00:00:00Z")
    assert "-" in ts
    assert tv.map_nuclear({"NewsCategory": "nuclear industry"}) == "nuclear"
    assert "href" in tv.create_hyperlink("https://example.com")

    df = pd.DataFrame(
        [
            {"topic": 1, "RelevantKeywords": "a,b", "NewsCategory": "nuclear industry", "AlertFlag": "Red", "URL": "https://example.com", "Title": "A"},
            {"topic": 2, "RelevantKeywords": "b,c", "NewsCategory": "health", "AlertFlag": "Yellow", "URL": "https://example.com/2", "Title": "B"},
        ]
    )
    enriched = tv.make_topic_keyword_column(df.copy())
    assert "topic_keyword" in enriched.columns

    opened = {"url": None}

    class DummyTrace:
        def __init__(self):
            self.customdata = [["https://example.com"]]
            self.clicked = None

        def on_click(self, cb):
            self.clicked = cb

    class DummyTreemap:
        def __init__(self):
            self.data = [DummyTrace()]

        def update_traces(self, **kwargs):
            return None

    class DummyFig:
        def __init__(self):
            self.data = []
            self.layout = SimpleNamespace(annotations=[SimpleNamespace(font=SimpleNamespace(update=lambda **kwargs: None))])

        def add_trace(self, trace, row=None, col=None):
            self.data.append(trace)

        def update_layout(self, **kwargs):
            return None

    monkeypatch.setattr(tv, "make_subplots", lambda *args, **kwargs: object())
    monkeypatch.setattr(tv.go, "FigureWidget", lambda *_args, **_kwargs: DummyFig())
    monkeypatch.setattr(tv.px, "treemap", lambda *_args, **_kwargs: DummyTreemap())
    monkeypatch.setattr(tv.webbrowser, "open_new_tab", lambda url: opened.__setitem__("url", url))

    fig = tv.create_two_treemaps(df.copy())
    assert fig is not None
    for trace in fig.data:
        trace.clicked(trace, SimpleNamespace(point_inds=[0]), None)
    assert opened["url"] == "https://example.com"

    over_time = pd.DataFrame(
        {
            "Timestamp": ["2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z"],
            "Topic": [0, 1],
            "Frequency": [1, 2],
            "Words": ["a", "b"],
        }
    )
    fig3d = tv.get_3d_time_plot(over_time)
    assert fig3d is not None

    images_dir = tmp_path / "images"
    data_dir = tmp_path / "data"
    model_dir = tmp_path / "models"
    images_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(tv, "_resolve_save_dirs", lambda: (images_dir, data_dir, model_dir))

    with pytest.raises(FileNotFoundError):
        tv.compute_topic_visualizations()

    (model_dir / "topic_model").mkdir(parents=True, exist_ok=True)
    with pytest.raises(FileNotFoundError):
        tv.compute_topic_visualizations()

    pd.DataFrame({"RelevantKeywords": ["x"], "Title": ["A"]}).to_csv(data_dir / "df_with_response_and_topics.csv", index=False)
    monkeypatch.setattr(tv, "generate_visualizations", lambda *args, **kwargs: "ok")
    monkeypatch.setattr(tv.BERTopic, "load", lambda *_args, **_kwargs: SimpleNamespace(transform=lambda docs: ([1], None)))
    assert tv.compute_topic_visualizations() == "ok"

    pd.DataFrame({"WrongCol": ["x"]}).to_csv(data_dir / "df_with_response_and_topics.csv", index=False)
    with pytest.raises(ValueError):
        tv.compute_topic_visualizations(config=SimpleNamespace(column_name="Missing"))


def test_get_visualize_hierarchy_with_ctfidf_and_hierarchical(monkeypatch):
    class DummyFig:
        def __init__(self):
            self.layout = {"yaxis": {"ticktext": [0, 1]}, "xaxis": {"ticktext": [0, 1]}}
            self.data = [{"x": np.array([1, 2, 3, 4]), "y": np.array([1, 2, 3, 4]), "text": ["a", "b", "c", "d"]}]
            self.added = 0

        def update_layout(self, **kwargs):
            return self

        def add_trace(self, *_args, **_kwargs):
            self.added += 1
            return None

        def __getitem__(self, key):
            if key == "data":
                return self.data
            raise KeyError(key)

    monkeypatch.setattr(tv.ff, "create_dendrogram", lambda *args, **kwargs: DummyFig())
    monkeypatch.setattr(tv, "validate_distance_matrix", lambda x, n: x)
    monkeypatch.setattr(
        tv,
        "_get_annotations",
        lambda **kwargs: [["a", "", "", "b"]],
    )

    topic_model = _dummy_topic_model()
    topic_model.c_tf_idf_ = np.array([[1.0, 0.0], [0.0, 1.0]])
    fig = tv.get_visualize_hierarchy(
        topic_model,
        hierarchical_topics=pd.DataFrame({"Parent_Name": ["P"], "Parent_ID": [1], "Topics": [[0, 1]]}),
        orientation="left",
    )
    assert fig is not None
    assert fig.added == 2


def test_get_annotations_multi_topic_branches(monkeypatch):
    monkeypatch.setattr(
        tv.sch,
        "dendrogram",
        lambda *args, **kwargs: {
            "leaves": [0, 1],
            "icoord": [[5, 6, 15, 16], [5, 6, 10, 11], [10, 11, 15, 16]],
        },
    )

    topic_model = _dummy_topic_model()
    topic_model.custom_labels_ = ["c0", "c1"]
    out = tv._get_annotations(
        topic_model=topic_model,
        hierarchical_topics=pd.DataFrame({"Parent_Name": ["P"], "Parent_ID": [99], "Topics": [[0, 1]]}),
        embeddings=np.array([[1.0, 0.0], [0.0, 1.0]]),
        linkage_function=lambda x: np.array([[0, 1, 0.5, 2]]),
        distance_function=lambda x: np.array([[0.0, 0.1], [0.1, 0.0]]),
        orientation="left",
        custom_labels=True,
    )
    assert isinstance(out, list)


def test_compute_topic_visualizations_column_fallback(tmp_path, monkeypatch):
    images_dir = tmp_path / "images"
    data_dir = tmp_path / "data"
    model_dir = tmp_path / "models"
    (model_dir / "topic_model").mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"RelevantKeywords": ["x"], "topic": [1], "Title": ["A"]}).to_csv(
        data_dir / "df_with_response_and_topics.csv", index=False
    )

    monkeypatch.setattr(tv, "_resolve_save_dirs", lambda: (images_dir, data_dir, model_dir))
    monkeypatch.setattr(tv.BERTopic, "load", lambda *_args, **_kwargs: SimpleNamespace())
    monkeypatch.setattr(tv, "generate_visualizations", lambda *args, **kwargs: "ok")
    cfg = SimpleNamespace(column_name="Missing")
    assert tv.compute_topic_visualizations(config=cfg) == "ok"
    assert cfg.column_name == "RelevantKeywords"
