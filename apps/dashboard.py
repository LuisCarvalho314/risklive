from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import streamlit as st

st.set_page_config(page_title="Risklive Dashboard", page_icon=":bar_chart:")

st.title("Risklive Dashboard")
st.info("UI placeholder. This will be replaced by the LangGraph-driven views.")
