from __future__ import annotations

import json
import pickle
import webbrowser
from collections import Counter
from typing import Callable, List, Union

import numpy as np
import pandas as pd
from bertopic._utils import validate_distance_matrix
from plotly.subplots import make_subplots
from scipy.cluster import hierarchy as sch
from scipy.sparse import csr_matrix
from sklearn.metrics.pairwise import cosine_similarity

import plotly.express as px
import plotly.figure_factory as ff
import plotly.graph_objects as go

from bertopic import BERTopic

from models.topic_model import TopicModelConfig, TopicVisualizations
from services.topic_modeling.modeling import _load_config_from_metadata, _normalize_keywords, _resolve_save_dirs


def get_visualize_hierarchy(
    topic_model,
    orientation: str = "left",
    topics: List[int] | None = None,
    top_n_topics: int | None = None,
    custom_labels: Union[bool, str] = False,
    title: str = "<b>Hierarchical Clustering</b>",
    width: int = 1000,
    height: int = 600,
    hierarchical_topics: pd.DataFrame | None = None,
    linkage_function: Callable[[csr_matrix], np.ndarray] | None = None,
    distance_function: Callable[[csr_matrix], csr_matrix] | None = None,
    color_threshold: int = 1,
) -> go.Figure:
    if distance_function is None:
        distance_function = lambda x: 1 - cosine_similarity(x)

    if linkage_function is None:
        linkage_function = lambda x: sch.linkage(x, "ward", optimal_ordering=True)

    freq_df = topic_model.get_topic_freq()
    freq_df = freq_df.loc[freq_df.Topic != -1, :]
    if topics is not None:
        topics = list(topics)
    elif top_n_topics is not None:
        topics = sorted(freq_df.Topic.to_list()[:top_n_topics])
    else:
        topics = sorted(freq_df.Topic.to_list())

    all_topics = sorted(list(topic_model.get_topics().keys()))
    indices = np.array([all_topics.index(topic) for topic in topics])

    if topic_model.c_tf_idf_ is not None:
        embeddings = topic_model.c_tf_idf_[indices]
    else:
        embeddings = np.array(topic_model.topic_embeddings_)[indices]

    if hierarchical_topics is not None and len(topics) == len(freq_df.Topic.to_list()):
        annotations = _get_annotations(
            topic_model=topic_model,
            hierarchical_topics=hierarchical_topics,
            embeddings=embeddings,
            distance_function=distance_function,
            linkage_function=linkage_function,
            orientation=orientation,
            custom_labels=custom_labels,
        )
    else:
        annotations = None

    distance_function_viz = lambda x: validate_distance_matrix(distance_function(x), embeddings.shape[0])

    fig = ff.create_dendrogram(
        embeddings,
        orientation=orientation,
        distfun=distance_function_viz,
        linkagefun=linkage_function,
        hovertext=annotations,
        color_threshold=color_threshold,
    )

    axis = "yaxis" if orientation == "left" else "xaxis"
    if isinstance(custom_labels, str):
        new_labels = [
            [[str(x), None]] + topic_model.topic_aspects_[custom_labels][x]
            for x in fig.layout[axis]["ticktext"]
        ]
        new_labels = ["_".join([label[0] for label in labels[:4]]) for labels in new_labels]
        new_labels = [label if len(label) < 30 else label[:27] + "..." for label in new_labels]
    elif topic_model.custom_labels_ is not None and custom_labels:
        new_labels = [topic_model.custom_labels_[topics[int(x)] + topic_model._outliers] for x in fig.layout[axis]["ticktext"]]
    else:
        new_labels = [
            [[str(topics[int(x)]), None]] + topic_model.get_topic(topics[int(x)])
            for x in fig.layout[axis]["ticktext"]
        ]
        new_labels = ["_".join([label[0] for label in labels[:1]]) for labels in new_labels[:1]]
        new_labels = [label if len(label) < 30 else label[:27] + "..." for label in new_labels]

    fig.update_layout(
        plot_bgcolor="#ECEFF1",
        template="plotly_white",
        title={
            "text": f"{title}",
            "x": 0.5,
            "xanchor": "center",
            "yanchor": "top",
            "font": dict(size=22, color="Black"),
        },
        hoverlabel=dict(bgcolor="white", font_size=16, font_family="Rockwell"),
    )

    if orientation == "left":
        fig.update_layout(height=200 + (15 * len(topics)), width=width, yaxis=dict(tickmode="array", ticktext=new_labels))
        y_max = max([trace["y"].max() + 5 for trace in fig["data"]])
        y_min = min([trace["y"].min() - 5 for trace in fig["data"]])
        fig.update_layout(yaxis=dict(range=[y_min, y_max]))
    else:
        fig.update_layout(width=600 + (15 * len(topics)), height=height, xaxis=dict(tickmode="array", ticktext=new_labels))

    if hierarchical_topics is not None:
        for index in [0, 3]:
            axis = "x" if orientation == "left" else "y"
            xs = [data["x"][index] for data in fig.data if (data["text"] and data[axis][index] > 0)]
            ys = [data["y"][index] for data in fig.data if (data["text"] and data[axis][index] > 0)]
            hovertext = [data["text"][index] for data in fig.data if (data["text"] and data[axis][index] > 0)]

            fig.add_trace(
                go.Scatter(x=xs, y=ys, marker_color="black", hovertext=hovertext, hoverinfo="text", mode="markers", showlegend=False)
            )
    return fig


def _get_annotations(
    topic_model,
    hierarchical_topics: pd.DataFrame,
    embeddings: csr_matrix,
    linkage_function: Callable[[csr_matrix], np.ndarray],
    distance_function: Callable[[csr_matrix], csr_matrix],
    orientation: str,
    custom_labels: bool = False,
) -> List[List[str]]:
    df = hierarchical_topics.loc[hierarchical_topics.Parent_Name != "Top", :]

    X = distance_function(embeddings)
    X = validate_distance_matrix(X, embeddings.shape[0])

    Z = linkage_function(X)
    P = sch.dendrogram(Z, orientation=orientation, no_plot=True)

    x_ticks = np.arange(5, len(P["leaves"]) * 10 + 5, 10)
    x_topic = dict(zip(P["leaves"], x_ticks))

    topic_vals = dict()
    for key, val in x_topic.items():
        topic_vals[val] = [key]

    parent_topic = dict(zip(df.Parent_ID, df.Topics))

    text_annotations = []
    for trace in P["icoord"]:
        fst_topic = topic_vals[trace[0]]
        scnd_topic = topic_vals[trace[2]]

        if len(fst_topic) == 1:
            if isinstance(custom_labels, str):
                fst_name = f"{fst_topic[0]}_" + "_".join(list(zip(*topic_model.topic_aspects_[custom_labels][fst_topic[0]]))[0][:3])
            elif topic_model.custom_labels_ is not None and custom_labels:
                fst_name = topic_model.custom_labels_[fst_topic[0] + topic_model._outliers]
            else:
                fst_name = "_".join([word for word, _ in topic_model.get_topic(fst_topic[0])][:5])
        else:
            for key, value in parent_topic.items():
                if set(value) == set(fst_topic):
                    fst_name = df.loc[df.Parent_ID == key, "Parent_Name"].values[0]

        if len(scnd_topic) == 1:
            if isinstance(custom_labels, str):
                scnd_name = f"{scnd_topic[0]}_" + "_".join(list(zip(*topic_model.topic_aspects_[custom_labels][scnd_topic[0]]))[0][:3])
            elif topic_model.custom_labels_ is not None and custom_labels:
                scnd_name = topic_model.custom_labels_[scnd_topic[0] + topic_model._outliers]
            else:
                scnd_name = "_".join([word for word, _ in topic_model.get_topic(scnd_topic[0])][:5])
        else:
            for key, value in parent_topic.items():
                if set(value) == set(scnd_topic):
                    scnd_name = df.loc[df.Parent_ID == key, "Parent_Name"].values[0]

        text_annotations.append([fst_name, "", "", scnd_name])

        center = (trace[0] + trace[2]) / 2
        topic_vals[center] = fst_topic + scnd_topic

    return text_annotations


def parse_timestamp(timestamp):
    dt = pd.to_datetime(timestamp)
    return dt.strftime("%d-%I%p")


def _write_json(path, payload: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))
    return str(path)


def _save_topic_keywords(images_dir, topic_model: BERTopic) -> str:
    topics = {}
    for topic_id, words in topic_model.get_topics().items():
        topics[str(topic_id)] = [word for word, _ in words]
    return _write_json(images_dir / "topic_keywords.json", topics)


def generate_visualizations(
    topic_model: BERTopic,
    docs: List[str],
    df: pd.DataFrame,
    images_dir,
    config: TopicModelConfig,
) -> TopicVisualizations:
    all_topics = [t for t in topic_model.get_topics().keys() if t != -1]
    all_topics = sorted(all_topics)
    selected_topics = all_topics[: config.max_topics]

    fig1 = topic_model.visualize_barchart(topics=selected_topics).to_json()
    (images_dir / "barchart.json").write_text(fig1)

    fig2 = topic_model.visualize_topics(width=1000, height=1000).to_json()
    (images_dir / "topics.json").write_text(fig2)

    fig3 = topic_model.visualize_documents(df["Title"].tolist()).to_json()
    (images_dir / "documents.json").write_text(fig3)

    if "Timestamp" in df.columns:
        valid_mask = df["Timestamp"].notna()
        docs_with_time = df.loc[valid_mask, config.column_name].tolist()
        timestamps = df.loc[valid_mask, "Timestamp"].tolist()
        topics_with_time = df.loc[valid_mask, "topic"].tolist()
        if docs_with_time and timestamps and topics_with_time:
            topics_over_time = topic_model.topics_over_time(
                docs_with_time,
                timestamps,
                topics=topics_with_time,
                nr_bins=20,
            )
            fig4 = topic_model.visualize_topics_over_time(topics_over_time).to_json()
            (images_dir / "topics_over_time.json").write_text(fig4)

    hierarchical_topics = topic_model.hierarchical_topics(docs)
    fig5 = get_visualize_hierarchy(
        topic_model=topic_model,
        hierarchical_topics=hierarchical_topics,
        orientation="bottom",
        width=3000,
        height=600,
    ).to_json()
    tree = topic_model.get_topic_tree(hierarchical_topics)
    (images_dir / "hierarchy.json").write_text(fig5)
    (images_dir / "topic_tree.txt").write_text(tree)

    fig7 = create_two_treemaps(df)
    with (images_dir / "treemap.pkl").open("wb") as f:
        pickle.dump(fig7, f)

    _save_topic_keywords(images_dir, topic_model)

    return TopicVisualizations(
        barchart_json=str(images_dir / "barchart.json"),
        topics_json=str(images_dir / "topics.json"),
        documents_json=str(images_dir / "documents.json"),
        topics_over_time_json=str(images_dir / "topics_over_time.json")
        if (images_dir / "topics_over_time.json").exists()
        else None,
        hierarchy_json=str(images_dir / "hierarchy.json"),
        topic_tree_txt=str(images_dir / "topic_tree.txt"),
        treemap_pkl=str(images_dir / "treemap.pkl"),
    )


def compute_topic_visualizations(config: TopicModelConfig | None = None) -> TopicVisualizations:
    images_dir, data_dir, model_dir = _resolve_save_dirs()
    model_path = model_dir / "topic_model"
    if not model_path.exists():
        raise FileNotFoundError(f"Missing topic model at {model_path}")

    if config is None:
        config = _load_config_from_metadata(images_dir) or TopicModelConfig()

    df_path = data_dir / "df_with_response_and_topics.csv"
    if not df_path.exists():
        raise FileNotFoundError(f"Missing topic model data at {df_path}")

    df = pd.read_csv(df_path)
    if config.column_name not in df.columns and "RelevantKeywords" in df.columns:
        config.column_name = "RelevantKeywords"
    if config.column_name not in df.columns:
        raise ValueError(f"Missing column for topic modeling: {config.column_name}")

    df[config.column_name] = df[config.column_name].apply(_normalize_keywords)
    docs = df[config.column_name].tolist()

    topic_model = BERTopic.load(str(model_path))
    if "topic" not in df.columns:
        topics, _ = topic_model.transform(docs)
        df["topic"] = topics

    return generate_visualizations(topic_model, docs, df, images_dir, config)


def get_3d_time_plot(topics_over_time):
    topics_over_time["timestamp"] = topics_over_time["Timestamp"].apply(parse_timestamp)
    unique_topics = topics_over_time["Topic"].unique()
    unique_timestamps = topics_over_time["timestamp"].unique()

    T, TP = np.meshgrid(range(len(unique_topics)), range(len(unique_timestamps)))
    frequencies = topics_over_time.pivot(index="timestamp", columns="Topic", values="Frequency").values
    frequencies = np.nan_to_num(frequencies)

    words = topics_over_time.pivot(index="timestamp", columns="Topic", values="Words").values

    surface = go.Surface(z=frequencies, x=T, y=TP, text=words, hoverinfo="text")
    fig = go.Figure(data=[surface])

    fig.update_layout(
        title={
            "text": "Topics Over Time 3D",
            "y": 0.9,
            "x": 0.5,
            "xanchor": "center",
            "font": {"size": 24},
            "yanchor": "top",
        },
        autosize=True,
        scene=dict(
            xaxis=dict(title="Topic", tickvals=np.arange(len(unique_topics)), ticktext=unique_topics),
            yaxis=dict(title="Time", tickvals=np.arange(len(unique_timestamps)), ticktext=unique_timestamps),
            zaxis=dict(title="Frequency"),
            camera=dict(eye=dict(x=1.5, y=1.5, z=1.5)),
        ),
        width=1000,
        height=700,
        margin=dict(l=65, r=50, b=65, t=90),
    )
    return fig


def map_nuclear(row):
    if row["NewsCategory"] == "nuclear industry":
        return "nuclear"
    return row["NewsCategory"]


def create_hyperlink(url):
    return f'<a href="{url}" style="cursor: pointer" target="_blank" rel="noopener noreferrer">🔗</a>'


def make_topic_keyword_column(df):
    df["RelevantKeywords_new"] = df["RelevantKeywords"].apply(_normalize_keywords)
    df["RelevantKeywords_new"] = df["RelevantKeywords_new"].apply(
        lambda value: [part.strip() for part in str(value).split(",") if part.strip()]
    )
    grouped = df.groupby("topic")["RelevantKeywords_new"].sum().reset_index()

    def get_top_2_keywords(keywords_list):
        all_keywords = [keyword for keyword in keywords_list]
        keyword_counts = Counter(all_keywords)
        top_2 = ", ".join([kw for kw, _ in keyword_counts.most_common(2)])
        return top_2

    grouped["topic_keyword"] = grouped["RelevantKeywords_new"].apply(get_top_2_keywords)
    df = df.merge(grouped[["topic", "topic_keyword"]], on="topic", how="left")
    return df


def create_two_treemaps(data):
    data = data[data.topic != -1]
    data = make_topic_keyword_column(data)
    data = data[data["AlertFlag"].isin(["Red", "Yellow"])]
    data["NewsCategory"] = data.apply(map_nuclear, axis=1)
    data["URL"] = data["URL"].apply(create_hyperlink)
    if not isinstance(data, pd.DataFrame):  # pragma: no cover
        data = pd.DataFrame(data)

    alert_levels = ["Red", "Yellow"]
    dataframes = {level: data[data["AlertFlag"] == level] for level in alert_levels}

    fig = go.FigureWidget(
        make_subplots(
            rows=2,
            cols=1,
            row_heights=[0.5, 0.5],
            specs=[[{"type": "treemap"}], [{"type": "treemap"}]],
            subplot_titles=("High Risk", "Medium Risk"),
            vertical_spacing=0.05,
        )
    )

    high_risk_treemap = px.treemap(
        dataframes["Red"],
        path=["AlertFlag", "NewsCategory", "topic_keyword", "RelevantKeywords", "URL", "Title"],
        color="AlertFlag",
        color_discrete_map={"Red": "red"},
        custom_data=["URL"],
    )

    high_risk_treemap.update_traces(
        hovertemplate='<span style="font-size: 20px;"><b>%{label}</b><br>Count: %{value}<br>',
        marker=dict(cornerradius=5),
        textfont=dict(size=25),
    )

    for trace in high_risk_treemap.data:
        fig.add_trace(trace, row=1, col=1)

    medium_risk_treemap = px.treemap(
        dataframes["Yellow"],
        path=["AlertFlag", "NewsCategory", "topic_keyword", "RelevantKeywords", "URL", "Title"],
        color="AlertFlag",
        color_discrete_map={"Yellow": "yellow"},
        custom_data=["URL"],
    )

    medium_risk_treemap.update_traces(
        hovertemplate='<span style="font-size: 20px;"><b>%{label}</b><br>Count: %{value}<br>',
        marker=dict(cornerradius=5),
        textfont=dict(size=25),
    )

    for trace in medium_risk_treemap.data:
        fig.add_trace(trace, row=2, col=1)

    def on_click(trace, points, state):
        if points.point_inds:
            ind = points.point_inds[0]
            url = trace.customdata[ind][0]
            if url and url != "nan":
                webbrowser.open_new_tab(url)

    for trace in fig.data:
        trace.on_click(on_click)

    fig.update_layout(
        height=800,
        margin=dict(t=80, l=25, r=25, b=25),
        title={
            "text": "<b>News Article Risk Assessment</b><br><sup>Categorized by Alert Level, News Category, Topic, and Keywords</sup>",
            "y": 0.98,
            "x": 0.5,
            "xanchor": "center",
            "yanchor": "top",
            "font": {"size": 24, "color": "black"},
        },
        clickmode="event+select",
    )

    for annotation in fig.layout.annotations:
        annotation.font.update(size=14)
    return fig
