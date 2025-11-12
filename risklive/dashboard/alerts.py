"""© 2025 University of Aberdeen. All rights reserved"""
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import pytz

# Load and preprocess data
data_path = "./results/data/news_data_with_llm_info.csv"
df = pd.read_csv(data_path)
df = df[df["Relevance"] == "Yes"]
df['Timestamp'] = pd.to_datetime(df['Timestamp'], format='ISO8601')
current_time = datetime.now(pytz.UTC)
five_hours_ago = current_time - timedelta(hours=5)

# Helper functions
def display_news_items(df, limit=10):
    df_sorted = df.sort_values(by=['AlertFlag', 'Timestamp'], 
                               ascending=[True, False], 
                               key=lambda x: pd.Categorical(x, categories=['Red', 'Yellow', 'Green'], ordered=True))
    df_sorted.drop_duplicates(subset=['Title'], keep='first', inplace=True)
    for _, row in df_sorted.head(limit).iterrows():
        emoji = {"Red": "🔴", "Yellow": "🟡", "Green": "🟢"}.get(row['AlertFlag'], "")
        st.markdown(f"{emoji} [{row['Title']}]({row['URL']})")

def display_news_with_alert(df, alert_color):
    df.drop_duplicates(subset=['Title'], keep='first', inplace=True)
    emoji = {"Red": "🔴", "Yellow": "🟡", "Green": "🟢"}
    for _, row in df[df['AlertFlag'] == alert_color].iterrows():
        st.markdown(f"{emoji[alert_color]} [{row['Title']}]({row['URL']})")

def display_news(df):
    df.drop_duplicates(subset=['Title'], keep='first', inplace=True)
    for _, row in df.iterrows():
        st.markdown(f"• [{row['Title']}]({row['URL']})")

# Main app
st.title("Summary of News")

# Nuclear Related News
with st.expander("Nuclear Related"):
    nuclear_df = df[df['NewsCategory'].isin(['nuclear', 'nuclear industry'])]
    
    for alert_color in ["Red", "Yellow", "Green"]:
        if not nuclear_df[nuclear_df['AlertFlag'] == alert_color].empty:
            display_news_with_alert(nuclear_df, alert_color)

# Non-Nuclear Related News
with st.expander("Non-Nuclear Related"):
    news_categories = ['geopolitical', 'supplychain', 'miscellaneous', 'health']

    for category in news_categories:
        category_df = df[df['NewsCategory'] == category]
        if not category_df.empty:
            st.subheader(f"{category.capitalize()}")
            display_news_items(category_df)

# News Alert Dashboard
st.title("News Alert Dashboard")

df_alerts = df[df['Timestamp'] > five_hours_ago]

for alert_color in ["Red", "Yellow", "Green"]:
    alert_df = df_alerts[df_alerts["AlertFlag"] == alert_color].sort_values(by="Timestamp", ascending=False)
    if not alert_df.empty:
        with st.expander(f"{'🔴' if alert_color == 'Red' else '🟡' if alert_color == 'Yellow' else '🟢'} {alert_color} Alerts"):
            display_news(alert_df)