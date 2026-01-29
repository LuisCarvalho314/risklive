from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class TopicModelConfig(BaseModel):
    embedding_model_name: str = "BAAI/bge-large-en-v1.5"
    column_name: str = "RelevantKeywords"
    random_state: int = 42
    umap_n_neighbors: int = 5
    umap_n_components: int = 5
    umap_min_dist: float = 0.0
    umap_metric: str = "cosine"
    hdbscan_min_cluster_size: int | None = None
    hdbscan_min_samples: int | None = None
    hdbscan_metric: str = "euclidean"
    hdbscan_cluster_selection_method: str = "eom"
    max_topics: int = 16
    embedding_batch_size: int | None = None
    embedding_show_progress: bool = False
    enable_visualizations: bool = True


class TopicAssignment(BaseModel):
    topic_id: int
    title: str
    timestamp: str | None = None


class TopicVisualizations(BaseModel):
    barchart_json: str | None = None
    topics_json: str | None = None
    documents_json: str | None = None
    topics_over_time_json: str | None = None
    hierarchy_json: str | None = None
    topic_tree_txt: str | None = None
    treemap_pkl: str | None = None


class TopicModelArtifacts(BaseModel):
    model_dir: str
    data_csv: str
    visualizations: TopicVisualizations = Field(default_factory=TopicVisualizations)
    assignments: List[TopicAssignment] = Field(default_factory=list)
