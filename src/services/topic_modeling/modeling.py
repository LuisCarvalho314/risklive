from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd
from bertopic import BERTopic
from hdbscan import HDBSCAN
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import CountVectorizer
from umap import UMAP

from config.settings import ROOT_DIR, get_config
from models.csv import LLMEnrichedRow
from models.topic_model import TopicAssignment, TopicModelArtifacts, TopicModelConfig, TopicVisualizations

logger = logging.getLogger(__name__)

_SENTENCE_MODEL_CACHE: dict[str, SentenceTransformer] = {}


def _resolve_dir(path: str) -> Path:
    base = Path(path)
    return base if base.is_absolute() else ROOT_DIR / base


def _normalize_keywords(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join([str(v) for v in value])
    return str(value)


def _hash_docs(docs: List[str]) -> str:
    joined = "\n".join(docs)
    return hashlib.sha256(joined.encode("utf-8", errors="ignore")).hexdigest()


def _get_sentence_model(name: str, cache: bool = True) -> SentenceTransformer:
    if cache and name in _SENTENCE_MODEL_CACHE:
        return _SENTENCE_MODEL_CACHE[name]
    model = SentenceTransformer(name)
    if cache:
        _SENTENCE_MODEL_CACHE[name] = model
    return model


def _prepare_dataframe(rows: List[LLMEnrichedRow], column_name: str) -> pd.DataFrame:
    df = pd.DataFrame([row.model_dump(by_alias=True) for row in rows])
    if column_name not in df.columns:
        raise ValueError(f"Missing column for topic modeling: {column_name}")
    df[column_name] = df[column_name].apply(_normalize_keywords)
    df = df.dropna(subset=[column_name])
    df = df[df[column_name].astype(str).str.strip() != ""]
    if "Timestamp" in df.columns:
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce", utc=True)
    return df


def initialize_models(len_docs: int, config: TopicModelConfig):
    sentence_model = _get_sentence_model(config.embedding_model_name, cache=True)
    vectorizer = CountVectorizer(stop_words="english")

    umap_model = UMAP(
        n_neighbors=config.umap_n_neighbors,
        n_components=config.umap_n_components,
        min_dist=config.umap_min_dist,
        metric=config.umap_metric,
        random_state=config.random_state,
    )

    if config.hdbscan_min_cluster_size is None or config.hdbscan_min_samples is None:
        if len_docs < 100:
            min_cluster_size, min_samples = 2, 2
        elif len_docs < 300:
            min_cluster_size, min_samples = 3, 3
        elif len_docs < 400:
            min_cluster_size, min_samples = 6, 6
        else:
            min_cluster_size, min_samples = 8, 8
    else:
        min_cluster_size = config.hdbscan_min_cluster_size
        min_samples = config.hdbscan_min_samples

    hdbscan_model = HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        metric=config.hdbscan_metric,
        cluster_selection_method=config.hdbscan_cluster_selection_method,
    )

    topic_model = BERTopic(
        embedding_model=sentence_model,
        umap_model=umap_model,
        hdbscan_model=hdbscan_model,
        vectorizer_model=vectorizer,
    )
    return sentence_model, topic_model


def batch_generate_embeddings(sentence_model: SentenceTransformer, docs: List[str], config: TopicModelConfig):
    kwargs = {"show_progress_bar": config.embedding_show_progress}
    if config.embedding_batch_size is not None:
        kwargs["batch_size"] = config.embedding_batch_size
    return sentence_model.encode(docs, **kwargs)


def train_topic_model(topic_model: BERTopic, docs: List[str], embeddings):
    topic_model.fit(docs, embeddings)


def _write_json(path: Path, payload: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))
    return str(path)


def _save_metadata(images_dir: Path, meta: dict) -> str:
    return _write_json(images_dir / "run_metadata.json", meta)


def _load_config_from_metadata(images_dir: Path) -> Optional[TopicModelConfig]:
    meta_path = images_dir / "run_metadata.json"
    if not meta_path.exists():
        return None
    try:
        payload = json.loads(meta_path.read_text())
        raw_config = payload.get("config")
        if isinstance(raw_config, dict):
            return TopicModelConfig(**raw_config)
    except Exception:
        return None
    return None

def _resolve_save_dirs() -> tuple[Path, Path, Path]:
    cfg = get_config()
    images_dir = _resolve_dir(cfg.save_dir.get("TOPIC_MODEL_IMAGE_DIR", "results/images"))
    data_dir = _resolve_dir(cfg.save_dir.get("CSV_DATA_DIR", "results/data"))
    model_dir = _resolve_dir(cfg.save_dir.get("TOPIC_MODEL_DIR", "results/models"))
    return images_dir, data_dir, model_dir


def save_core_artifacts(topic_model: BERTopic, df: pd.DataFrame, config: TopicModelConfig) -> tuple[Path, Path, Path]:
    images_dir, data_dir, model_dir = _resolve_save_dirs()

    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(model_dir, exist_ok=True)

    topic_model.save(
        os.path.join(model_dir, "topic_model"),
        serialization="safetensors",
        save_ctfidf=True,
        save_embedding_model=config.embedding_model_name,
    )
    df.to_csv(os.path.join(data_dir, "df_with_response_and_topics.csv"), index=False)

    return images_dir, data_dir, model_dir


def compute_topic_modeling(rows: List[LLMEnrichedRow], config: TopicModelConfig | None = None) -> TopicModelArtifacts:
    config = config or TopicModelConfig()
    start = time.time()

    df = _prepare_dataframe(rows, config.column_name)
    docs = df[config.column_name].tolist()
    if not docs:
        raise ValueError("No documents provided for topic modeling")

    sentence_model, topic_model = initialize_models(len(docs), config)
    embeddings = batch_generate_embeddings(sentence_model, docs, config)
    train_topic_model(topic_model, docs, embeddings)

    df["topic"] = topic_model.topics_
    images_dir, data_dir, model_dir = save_core_artifacts(topic_model, df, config)

    meta = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "doc_count": len(docs),
        "config": config.model_dump(),
        "duration_seconds": round(time.time() - start, 3),
        "docs_hash": _hash_docs(docs),
    }
    _save_metadata(images_dir, meta)

    assignments = []
    if "topic" in df.columns:
        for _, row in df.iterrows():
            assignments.append(
                TopicAssignment(
                    topic_id=int(row.get("topic", -1)),
                    title=str(row.get("Title", "")),
                    timestamp=str(row.get("Timestamp", "")) if row.get("Timestamp") is not None else None,
                )
            )

    return TopicModelArtifacts(
        model_dir=str(model_dir / "topic_model"),
        data_csv=str(data_dir / "df_with_response_and_topics.csv"),
        visualizations=TopicVisualizations(),
        assignments=assignments,
    )
