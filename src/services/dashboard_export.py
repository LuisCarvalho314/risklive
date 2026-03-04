"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List

import polars as pl

from config import settings as settings_module
from models.dashboard import (
    AlertItem,
    AlertsSection,
    DashboardModel,
    FlaggedAlerts,
    RecentAlerts,
    TopicEntry,
    TreemapNode,
)
from utils.logging import get_logger, log_artifact_written

ROOT = Path(__file__).resolve().parents[2]
logger = get_logger(__name__)

ALERT_ORDER = ["Red", "Yellow", "Green"]
NUCLEAR_CATEGORIES = ["nuclear", "nuclear industry"]
NON_NUCLEAR_CATEGORIES = ["geopolitical", "supplychain", "miscellaneous", "health"]
ALERT_WEIGHT = {"Red": 5.0, "Yellow": 3.0, "Green": 1.0}


def _data_path(filename: str, key: str = "CSV_DATA_DIR", default: str = "results/data/") -> Path:
    cfg = settings_module.get_config()
    data_dir = cfg.save_dir.get(key, default)
    path = Path(data_dir)
    if not path.is_absolute():
        path = settings_module.ROOT_DIR / path
    return path / filename


def _safe_str(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value != value:
        return ""
    return str(value)


def _safe_timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, float) and value != value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            return None
    return None


def load_news() -> pl.DataFrame:
    data_path = _data_path("news_data_with_llm_info.csv")
    if not data_path.exists():
        return pl.DataFrame()
    df = pl.read_csv(data_path)
    df = _merge_topics(df)
    if "Relevance" in df.columns:
        df = df.filter(pl.col("Relevance") == "Yes")
    if "Timestamp" in df.columns:
        df = df.with_columns(
            pl.col("Timestamp")
            .cast(pl.Utf8)
            .str.to_datetime(strict=False, time_zone="UTC")
            .alias("Timestamp")
        )
    return df


def _merge_topics(df: pl.DataFrame) -> pl.DataFrame:
    topics_path = _data_path("df_with_response_and_topics.csv")
    if not topics_path.exists() or df.is_empty():
        return df
    topics_df = pl.read_csv(topics_path)
    if "topic" not in topics_df.columns:
        return df

    def _is_empty(series: pl.Series) -> bool:
        if series.len() == 0:  # pragma: no cover
            return True
        values = [str(val or "").strip() for val in series.to_list()]
        return all(v == "" for v in values)

    if "topic" in df.columns and not _is_empty(df.get_column("topic")):
        return df

    merged = df.clone()
    if "URL" in df.columns and "URL" in topics_df.columns:
        merged = merged.join(
            topics_df.select(["URL", "topic"]),
            on="URL",
            how="left",
            suffix="_topic",
        )
        if "topic_topic" in merged.columns:
            merged = merged.with_columns(
                pl.when(pl.col("topic").fill_null("").str.strip_chars() != "")
                .then(pl.col("topic").fill_null(""))
                .otherwise(pl.col("topic_topic").fill_null(""))
                .alias("topic")
            ).drop("topic_topic")

    if "topic" in merged.columns and not _is_empty(merged.get_column("topic")):
        return _attach_topic_keywords(merged)

    if "Title" in df.columns and "Title" in topics_df.columns:
        merged = df.join(
            topics_df.select(["Title", "topic"]),
            on="Title",
            how="left",
            suffix="_topic",
        )
        if "topic_topic" in merged.columns:
            merged = merged.with_columns(
                pl.when(pl.col("topic").fill_null("").str.strip_chars() != "")
                .then(pl.col("topic").fill_null(""))
                .otherwise(pl.col("topic_topic").fill_null(""))
                .alias("topic")
            ).drop("topic_topic")

    return _attach_topic_keywords(merged)


def _attach_topic_keywords(df: pl.DataFrame) -> pl.DataFrame:
    if df.is_empty() or "topic" not in df.columns or "RelevantKeywords" not in df.columns:
        return df
    keywords_by_topic: Dict[str, Counter] = {}
    for row in df.select(["topic", "RelevantKeywords"]).iter_rows(named=True):
        topic = _safe_str(row.get("topic", ""))
        raw = _safe_str(row.get("RelevantKeywords", ""))
        if not topic or not raw:
            continue
        parts = [kw.strip() for kw in raw.split(",") if kw.strip()]
        if not parts:
            continue
        counter = keywords_by_topic.setdefault(topic, Counter())
        counter.update(parts)

    topic_keyword = {}
    for topic, counter in keywords_by_topic.items():
        topic_keyword[topic] = ", ".join([kw for kw, _ in counter.most_common(2)])

    return df.with_columns(
        pl.col("topic")
        .map_elements(lambda value: topic_keyword.get(_safe_str(value), ""), return_dtype=pl.Utf8)
        .alias("topic_keyword")
    )


def _alert_item_from_row(row: dict) -> AlertItem:
    return AlertItem(
        title=_safe_str(row.get("Title", "")),
        url=_safe_str(row.get("URL", "")) or None,
        description=_safe_str(row.get("Description", "")),
        timestamp=_safe_timestamp(row.get("Timestamp")),
        alert_flag=_safe_str(row.get("AlertFlag", "")),
        alert_reason=_safe_str(row.get("AlertReason", "")),
        news_category=_safe_str(row.get("NewsCategory", "")),
        short_summary=_safe_str(row.get("ShortSummary", "")),
        relevance=_safe_str(row.get("Relevance", "")),
    )


def _sort_by_alert_and_time(df: pl.DataFrame) -> pl.DataFrame:
    if df.is_empty():
        return df
    if "AlertFlag" not in df.columns:
        return df
    return df.with_columns(
        pl.when(pl.col("AlertFlag") == "Red")
        .then(0)
        .when(pl.col("AlertFlag") == "Yellow")
        .then(1)
        .when(pl.col("AlertFlag") == "Green")
        .then(2)
        .otherwise(3)
        .alias("_alert_order")
    ).sort(["_alert_order", "Timestamp"], descending=[False, True]).drop("_alert_order")


def build_alerts(df: pl.DataFrame) -> AlertsSection:
    if df.is_empty():
        return AlertsSection()

    if "Title" in df.columns:
        df = df.unique(subset=["Title"], keep="first")

    nuclear_items: List[AlertItem] = []
    nuclear_df = (
        df.filter(pl.col("NewsCategory").is_in(NUCLEAR_CATEGORIES))
        if "NewsCategory" in df.columns
        else df
    )
    for alert_color in ALERT_ORDER:
        if "AlertFlag" not in nuclear_df.columns:
            break
        color_df = nuclear_df.filter(pl.col("AlertFlag") == alert_color)
        for row in color_df.iter_rows(named=True):
            nuclear_items.append(_alert_item_from_row(row))

    non_nuclear: Dict[str, List[AlertItem]] = {}
    for category in NON_NUCLEAR_CATEGORIES:
        if "NewsCategory" not in df.columns:
            break
        category_df = df.filter(pl.col("NewsCategory") == category)
        if category_df.is_empty():
            continue
        category_df = _sort_by_alert_and_time(category_df)
        if "Title" in category_df.columns:
            category_df = category_df.unique(subset=["Title"], keep="first")
        items = [_alert_item_from_row(row) for row in category_df.head(10).iter_rows(named=True)]
        if items:
            non_nuclear[category] = items

    return AlertsSection(nuclear=nuclear_items, non_nuclear=non_nuclear)


def build_recent_alerts(df: pl.DataFrame) -> RecentAlerts:
    if df.is_empty():
        return RecentAlerts()

    now = datetime.now(timezone.utc)
    five_hours_ago = now - timedelta(hours=5)
    if "Timestamp" in df.columns:
        df_alerts = df.filter(pl.col("Timestamp") > five_hours_ago)
    else:
        df_alerts = df

    def _color_alerts(color: str) -> List[AlertItem]:
        if "AlertFlag" not in df_alerts.columns:
            return []
        color_df = (
            df_alerts.filter(pl.col("AlertFlag") == color)
            .sort("Timestamp", descending=True)
        )
        if "Title" in color_df.columns:
            color_df = color_df.unique(subset=["Title"], keep="first")
        return [_alert_item_from_row(row) for row in color_df.iter_rows(named=True)]

    return RecentAlerts(
        red=_color_alerts("Red"),
        yellow=_color_alerts("Yellow"),
        green=_color_alerts("Green"),
    )


def build_flagged_alerts(df: pl.DataFrame) -> FlaggedAlerts:
    if df.is_empty():
        return FlaggedAlerts()

    def _color_alerts(color: str) -> List[AlertItem]:
        if "AlertFlag" not in df.columns:
            return []
        color_df = df.filter(pl.col("AlertFlag") == color).sort("Timestamp", descending=True)
        if "Title" in color_df.columns:
            color_df = color_df.unique(subset=["Title"], keep="first")
        return [_alert_item_from_row(row) for row in color_df.iter_rows(named=True)]

    return FlaggedAlerts(
        red=_color_alerts("Red"),
        yellow=_color_alerts("Yellow"),
    )


def build_newsmap(df: pl.DataFrame) -> TreemapNode:
    root = TreemapNode(name="All News", children=[])
    if df.is_empty() or "NewsCategory" not in df.columns:
        return root

    now = datetime.now(timezone.utc)

    def _value_for_row(row: pd.Series) -> float:
        alert_flag = _safe_str(row.get("AlertFlag", ""))
        weight = ALERT_WEIGHT.get(alert_flag, 1.0)
        timestamp = _safe_timestamp(row.get("Timestamp"))
        if not timestamp:
            return weight
        age_hours = max(0.0, (now - timestamp).total_seconds() / 3600)
        recency = max(0.35, 1.5 - (age_hours / 24.0))
        return weight * recency

    categories = sorted(
        [cat for cat in df.get_column("NewsCategory").drop_nulls().unique().to_list() if str(cat).strip()]
    )
    for category in categories:
        cat_df = df.filter(pl.col("NewsCategory") == category)
        if cat_df.is_empty():
            continue
        cat_node = TreemapNode(name=str(category), children=[])
        for alert_color in ALERT_ORDER:
            if "AlertFlag" not in cat_df.columns:
                break
            color_df = cat_df.filter(pl.col("AlertFlag") == alert_color)
            if color_df.is_empty():
                continue
            color_node = TreemapNode(name=alert_color, children=[])
            for row in color_df.iter_rows(named=True):
                title = _safe_str(row.get("Title", "")) or "Untitled"
                timestamp = _safe_timestamp(row.get("Timestamp"))
                meta = {
                    "title": title,
                    "url": _safe_str(row.get("URL", "")) or None,
                    "category": _safe_str(row.get("NewsCategory", "")),
                    "alertFlag": _safe_str(row.get("AlertFlag", "")),
                    "alertReason": _safe_str(row.get("AlertReason", "")),
                    "timestamp": timestamp.isoformat() if timestamp else None,
                    "shortSummary": _safe_str(row.get("ShortSummary", "")),
                    "description": _safe_str(row.get("Description", "")),
                    "topic": _safe_str(row.get("topic", "")),
                    "topicLabel": _safe_str(row.get("topic_keyword", "")),
                }
                color_node.children.append(
                    TreemapNode(name=title, value=_value_for_row(row), meta=meta)
                )
            if color_node.children:
                cat_node.children.append(color_node)
        if cat_node.children:
            root.children.append(cat_node)

    def _rollup(node: TreemapNode) -> float:
        if not node.children:
            return float(node.value or 0)
        total = 0.0
        for child in node.children:
            total += _rollup(child)
        node.value = total
        return total

    _rollup(root)
    return root


def load_topics() -> List[TopicEntry]:
    report_path = _data_path("df_report.csv")
    if not report_path.exists():
        return []
    try:
        df = pl.read_csv(report_path)
    except pl.exceptions.NoDataError:
        return []
    if "keyword" not in df.columns or "response" not in df.columns:
        return []
    df = df.select(["keyword", "response"]).drop_nulls()
    return [
        TopicEntry(keyword=_safe_str(row.get("keyword")), response=_safe_str(row.get("response")))
        for row in df.iter_rows(named=True)
    ]


def load_topic_tree() -> str:
    tree_path = _data_path("topic_tree.txt", key="TOPIC_MODEL_IMAGE_DIR", default="results/images/")
    if not tree_path.exists():
        return ""
    return tree_path.read_text(encoding="utf-8")


def main() -> None:
    df = load_news()
    alerts = build_alerts(df)
    recent_alerts = build_recent_alerts(df)
    flagged_alerts = build_flagged_alerts(df)
    newsmap = build_newsmap(df)
    topics = load_topics()
    topic_tree = load_topic_tree()

    dashboard = DashboardModel(
        generated_at=datetime.now(timezone.utc),
        alerts=alerts,
        recent_alerts=recent_alerts,
        flagged_alerts=flagged_alerts,
        newsmap=newsmap,
        topics=topics,
        topic_tree=topic_tree,
    )

    output_path = settings_module.ROOT_DIR / "results" / "web" / "dashboard.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(dashboard.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    log_artifact_written(
        logger,
        stage="dashboard_export",
        operation="export_dashboard",
        component="services.dashboard_export",
        artifact_path=output_path,
        artifact_type="json",
    )

    schema = DashboardModel.model_json_schema()
    schema_path = settings_module.ROOT_DIR / "results" / "web" / "dashboard.schema.json"
    schema_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    log_artifact_written(
        logger,
        stage="dashboard_export",
        operation="export_dashboard",
        component="services.dashboard_export",
        artifact_path=schema_path,
        artifact_type="json",
    )

    # web_schema_path = settings_module.ROOT_DIR / "web" / "schema" / "dashboard.schema.json"
    # web_schema_path.parent.mkdir(parents=True, exist_ok=True)
    # web_schema_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    # log_artifact_written(
    #     logger,
    #     stage="dashboard_export",
    #     operation="export_dashboard",
    #     component="services.dashboard_export",
    #     artifact_path=web_schema_path,
    #     artifact_type="json",
    # )


if __name__ == "__main__":  # pragma: no cover
    main()
