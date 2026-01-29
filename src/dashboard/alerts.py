"""Streamlit dashboard for alert summaries."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pytz
import streamlit as st

import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from config.settings import ROOT_DIR, get_config


def _data_path(filename: str) -> Path:
    cfg = get_config()
    data_dir = cfg.save_dir.get("CSV_DATA_DIR", "results/data/")
    path = Path(data_dir)
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path / filename


def load_data() -> pd.DataFrame:
    data_path = _data_path("news_data_with_llm_info.csv")
    if not data_path.exists():
        return pd.DataFrame()
    df = pd.read_csv(data_path)
    if "Relevance" in df.columns:
        df = df[df["Relevance"] == "Yes"]
    if "Timestamp" in df.columns:
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce", utc=True)
    return df


def display_news_items(df: pd.DataFrame, limit: int = 10) -> None:
    df_sorted = df.sort_values(
        by=["AlertFlag", "Timestamp"],
        ascending=[True, False],
        key=lambda x: pd.Categorical(x, categories=["Red", "Yellow", "Green"], ordered=True),
    )
    df_sorted.drop_duplicates(subset=["Title"], keep="first", inplace=True)
    for _, row in df_sorted.head(limit).iterrows():
        emoji = {"Red": "🔴", "Yellow": "🟡", "Green": "🟢"}.get(row.get("AlertFlag", ""), "")
        st.markdown(f"{emoji} [{row.get('Title','')}]({row.get('URL','')})")


def display_news_with_alert(df: pd.DataFrame, alert_color: str) -> None:
    df.drop_duplicates(subset=["Title"], keep="first", inplace=True)
    emoji = {"Red": "🔴", "Yellow": "🟡", "Green": "🟢"}
    for _, row in df[df["AlertFlag"] == alert_color].iterrows():
        st.markdown(f"{emoji.get(alert_color, '')} [{row.get('Title','')}]({row.get('URL','')})")


def display_news(df: pd.DataFrame) -> None:
    df.drop_duplicates(subset=["Title"], keep="first", inplace=True)
    for _, row in df.iterrows():
        st.markdown(f"• [{row.get('Title','')}]({row.get('URL','')})")


def main() -> None:
    df = load_data()
    if df.empty:
        st.title("Summary of News")
        st.warning("No data available.")
        return

    st.title("Summary of News")

    with st.expander("Nuclear Related"):
        nuclear_df = df[df["NewsCategory"].isin(["nuclear", "nuclear industry"])]
        for alert_color in ["Red", "Yellow", "Green"]:
            if not nuclear_df[nuclear_df["AlertFlag"] == alert_color].empty:
                display_news_with_alert(nuclear_df, alert_color)

    with st.expander("Non-Nuclear Related"):
        news_categories = ["geopolitical", "supplychain", "miscellaneous", "health"]
        for category in news_categories:
            category_df = df[df["NewsCategory"] == category]
            if not category_df.empty:
                st.subheader(category.capitalize())
                display_news_items(category_df)

    st.title("News Alert Dashboard")
    current_time = datetime.now(pytz.UTC)
    five_hours_ago = current_time - timedelta(hours=5)
    if "Timestamp" in df.columns:
        df_alerts = df[df["Timestamp"] > five_hours_ago]
    else:
        df_alerts = df

    for alert_color in ["Red", "Yellow", "Green"]:
        alert_df = df_alerts[df_alerts["AlertFlag"] == alert_color].sort_values(
            by="Timestamp", ascending=False
        )
        if not alert_df.empty:
            with st.expander(
                f"{'🔴' if alert_color == 'Red' else '🟡' if alert_color == 'Yellow' else '🟢'} {alert_color} Alerts"
            ):
                display_news(alert_df)


if __name__ == "__main__":
    main()
