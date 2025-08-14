import os
import requests
import pandas as pd
from datetime import datetime, timedelta
from risklive.config import SERPAPI_API_KEY, CATEGORIES, QUERIES
import logging

logger = logging.getLogger(__name__)

class SerpNewsAPI:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://serpapi.com/search"

    def search_news(self, query, date_from=None, is_trending=False):
        params = {
            "engine": "google_news",
            "q": query,
            "api_key": self.api_key,
            "hl": "en",
            "gl": "gb",
            "num": 100,
        }
        if date_from:
            params["tbs"] = f"cdr:1,cd_min:{date_from},cd_max:{datetime.now().strftime('%Y-%m-%d')}"

        response = requests.get(self.base_url, params=params)
        response.raise_for_status()
        return response.json()

def search_news(query, since):
    serp_api = SerpNewsAPI(api_key=SERPAPI_API_KEY)
    date_str = datetime.fromtimestamp(since).strftime('%Y-%m-%d')
    data = serp_api.search_news(query=query, date_from=date_str)
    articles = data.get("news_results", [])
    rows = [(a.get("title"), a.get("link"), a.get("snippet"), a.get("date"), "no") for a in articles]
    return pd.DataFrame(rows, columns=['Title', 'URL', 'Description', 'Timestamp', 'IsTrending'])

def extract_trending_topics(since):
    # Placeholder: no trending endpoint in SerpAPI, use top news instead
    serp_api = SerpNewsAPI(api_key=SERPAPI_API_KEY)
    date_str = datetime.fromtimestamp(since).strftime('%Y-%m-%d')
    data = serp_api.search_news(query="top news", date_from=date_str)
    articles = data.get("news_results", [])
    topics = [(a.get("title"), a.get("link"), a.get("link"), True) for a in articles]
    return pd.DataFrame(topics, columns=['Name', 'WebSearchURL', 'NewsSearchURL', 'IsBreakingNews'])

def extract_news_by_category(category, since):
    return search_news(query=category, since=since)

def search_news_for_trending_topics(since):
    trending_df = extract_trending_topics(since)
    serp_api = SerpNewsAPI(api_key=SERPAPI_API_KEY)
    all_articles = []
    for _, row in trending_df.iterrows():
        topic = row['Name']
        data = serp_api.search_news(query=topic, is_trending=True)
        articles = data.get("news_results", [])
        all_articles.extend([
            (a.get("title"), a.get("link"), a.get("snippet"), a.get("date"), "yes") for a in articles
        ])
    return pd.DataFrame(all_articles, columns=['Title', 'URL', 'Description', 'Timestamp', 'IsTrending'])

def aggregate_news_data(is_trending=True, days=3, save_folder=None):
    full_df = pd.DataFrame()
    since_ts = int((datetime.now() - timedelta(days=days)).timestamp())

    if is_trending:
        trending_df = search_news_for_trending_topics(since_ts)
        full_df = pd.concat([full_df, trending_df])

    for category in CATEGORIES:
        cat_df = extract_news_by_category(category, since_ts)
        full_df = pd.concat([full_df, cat_df])

    for query in QUERIES:
        query_df = search_news(query=query, since=since_ts)
        full_df = pd.concat([full_df, query_df])

    full_df.drop_duplicates(subset=["URL"], inplace=True)
    full_df.dropna(subset=["Description"], inplace=True)
    if save_folder:
        os.makedirs(save_folder, exist_ok=True)
        full_df.to_csv(f"{save_folder}/news_data.csv", index=False)
    return full_df

# Optional wrappers
def aggregate_trending_news(days=1, save_folder=None):
    return aggregate_news_data(is_trending=True, days=days, save_folder=save_folder)

def aggregate_regular_news(hours=1, save_folder=None):
    days = hours / 24
    return aggregate_news_data(is_trending=False, days=days, save_folder=save_folder)
