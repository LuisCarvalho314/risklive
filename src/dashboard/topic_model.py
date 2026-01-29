"""Streamlit dashboard for topic modeling artifacts."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.io as pio
import streamlit as st
import streamlit_analytics2 as streamlit_analytics
import pickle

import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from config.settings import ROOT_DIR, get_config

st.set_page_config(page_title="Risk Live", page_icon=":star", layout="wide")

margins_css = """
<style>
.appview-container .main .block-container{
        padding-left: 0rem;
        }
</style>
"""

st.markdown(margins_css, unsafe_allow_html=True)


def _path_from_save_dir(key: str, filename: str) -> Path:
    cfg = get_config()
    base = Path(cfg.save_dir.get(key, "results"))
    if not base.is_absolute():
        base = ROOT_DIR / base
    return base / filename


def get_figures():
    img_dir = _path_from_save_dir("TOPIC_MODEL_IMAGE_DIR", "")
    report_path = _path_from_save_dir("CSV_DATA_DIR", "df_report.csv")

    json_files = ["topics.json", "barchart.json", "topics_over_time.json", "documents.json", "hierarchy.json"]
    json_figures = []
    for file in json_files:
        path = img_dir / file
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as handle:
            try:
                fig = pio.from_json(handle.read())
            except Exception:
                # Skip non-plotly JSON artifacts (e.g., placeholder outputs)
                continue
            json_figures.append(fig)

    tree_path = img_dir / "topic_tree.txt"
    tree = tree_path.read_text() if tree_path.exists() else ""
    treemap_path = img_dir / "treemap.pkl"
    treemap_fig = None
    if treemap_path.exists():
        try:
            with treemap_path.open("rb") as handle:
                treemap_fig = pickle.load(handle)
        except Exception:
            treemap_fig = None
    return json_figures, treemap_fig, tree, report_path


def get_report(report_path: Path) -> pd.DataFrame:
    if not report_path.exists():
        return pd.DataFrame()
    df = pd.read_csv(report_path)
    if "keyword" in df.columns and "response" in df.columns:
        return df[["keyword", "response"]]
    return df


def main():
    st.title("Risk Live: Topic Modeling")
    st.write(
        "This app applies topic modeling on news articles from the past 72 hours and visualizes them."
    )

    json_figures, treemap_fig, tree, report_path = get_figures()
    with st.expander("Daily Report"):
        df = get_report(report_path)
        if df is None or df.empty:
            st.warning("No high risk reports available.")
        else:
            topics = df["keyword"].dropna().unique().tolist() if "keyword" in df.columns else []
            if not topics:
                st.warning("No topics available.")
            else:
                keyword = st.selectbox("Select Topic", topics, key="topic_selector")
                response_series = df.loc[df["keyword"] == keyword, "response"]
                if response_series.empty:
                    st.warning("No response found for the selected topic.")
                else:
                    st.write(response_series.iloc[0])

    with st.expander("Topic Tree"):
        st.text(tree)

    if treemap_fig is not None:
        st.plotly_chart(treemap_fig, use_container_width=True)
    for fig in json_figures:
        st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__":
    with streamlit_analytics.track():
        main()
