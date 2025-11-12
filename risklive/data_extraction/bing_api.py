"""© 2025 University of Aberdeen. All rights reserved"""
import os
import requests
import pandas as pd
from datetime import datetime
from risklive.config import BING_API_KEY, CATEGORIES, QUERIES
import logging
logger = logging.getLogger(__name__)

class BingAPI:
    def __init__(self, api_key):
        self.api_key = api_key
        self.trending_endpoint = "https://api.bing.microsoft.com/v7.0/news/trendingtopics"
        self.news_endpoint = "https://api.bing.microsoft.com/v7.0/news"
        self.search_endpoint = "https://api.bing.microsoft.com/v7.0/news/search"
        
    def get_trending_topics(self, since, market='en-GB'):
        headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        params = {
            "mkt": market,
            "since": since,
            "sortBy": "Date"
        }
        response = requests.get(self.trending_endpoint, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

    def get_news_by_category(self, category, since, market='en-GB'):
        headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        params = {
            "category": category,
            "since": since,
            "mkt": market,
            "sortBy": "Date"
        }
        response = requests.get(self.news_endpoint, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    
    def search_news(self, query, istrending=False, since=None):
        headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        if istrending:
            params = {
                "q": query,
                "count": 1,
                "freshness": "Day",
                "sortBy": "Relevance",
            }
        else:
            params = {
                "q": query,
                "count": 100,
                "freshness": "Day",
                "sortBy": "Date",
                "since": since
            }
        response = requests.get(self.search_endpoint, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

def extract_trending_topics(since):
    bing_api = BingAPI(api_key=BING_API_KEY)    
    trending_data = bing_api.get_trending_topics(since)
    topics = [(topic['name'], topic['webSearchUrl'], topic['newsSearchUrl'], topic['isBreakingNews']) for topic in trending_data['value']]
    return pd.DataFrame(topics, columns=['Name', 'WebSearchURL', 'NewsSearchURL', 'IsBreakingNews'])

def extract_news_by_category(category, since):
    bing_api = BingAPI(api_key=BING_API_KEY)
    news_data = bing_api.get_news_by_category(category=category, since=since)
    # append a 5second delta to the timestamp to ensure uniqueness
    articles = [(article['name'], article['url'], article['description'], article['datePublished'], "no") for article in news_data['value']]
    
    return pd.DataFrame(articles, columns=['Title', 'URL', 'Description', 'Timestamp', 'IsTrending'])

def search_news(query, since):
    bing_api = BingAPI(api_key=BING_API_KEY)
    search_data = bing_api.search_news(query=query, since=since)
    timestamp = datetime.now().isoformat()
    articles = [(article['name'], article['url'], article['description'], article['datePublished'], "no") for article in search_data['value']]
    return pd.DataFrame(articles, columns=['Title', 'URL', 'Description', 'Timestamp', 'IsTrending'])

def search_news_for_trending_topics(since):
    trending_topics_df = extract_trending_topics(since)
    bing_api = BingAPI(api_key=BING_API_KEY)
    all_articles = []
    
    for index, row in trending_topics_df.iterrows():
        topic_name = row['Name']
        search_data = bing_api.search_news(query=topic_name, istrending=True)
        timestamp = datetime.now().isoformat()
        articles = [(article['name'], article['url'], article['description'], article['datePublished'], 'yes') for article in search_data['value']]
        all_articles.extend(articles)
    
    return pd.DataFrame(all_articles, columns=['Title', 'URL', 'Description', 'Timestamp', 'IsTrending'])

def aggregate_trending_news(days=1, save_folder = None):
    logger.debug(f"Starting aggregate_trending_news function")
    if save_folder and os.path.exists(f"{save_folder}/news_data.csv"):
        full_news_df = pd.read_csv(f"{save_folder}/news_data.csv")
    else:
        full_news_df = pd.DataFrame()
    since_date = int((datetime.now() - pd.DateOffset(days=days)).timestamp())
    trending_topics_df = search_news_for_trending_topics(since_date)
    
    full_news_df = pd.concat([full_news_df, trending_topics_df]).drop_duplicates(subset=['URL'], keep='first')
        
    full_news_df.dropna(subset=['Description'], inplace=True)
    if save_folder:
        os.makedirs(save_folder, exist_ok=True)
        full_news_df.to_csv(f"{save_folder}/news_data.csv", index=False)
    return full_news_df

def aggregate_regular_news(hours=1, save_folder = None):
    if save_folder and os.path.exists(f"{save_folder}/news_data.csv"):
        full_news_df = pd.read_csv(f"{save_folder}/news_data.csv")
    else:
        full_news_df = pd.DataFrame()
        
    since_date = int((datetime.now() - pd.DateOffset(hours=hours)).timestamp())
    for category in CATEGORIES:
        news_by_category_df = extract_news_by_category(category=category, since = since_date)
        full_news_df = pd.concat([full_news_df, news_by_category_df]).drop_duplicates(subset=['URL'], keep='first')
    
    for query in QUERIES:
        search_news_df = search_news(query=query, since=since_date)
        full_news_df = pd.concat([full_news_df, search_news_df]).drop_duplicates(subset=['URL'], keep='first')

    full_news_df.dropna(subset=['Description'], inplace=True)
    if save_folder:
        os.makedirs(save_folder, exist_ok=True)
        full_news_df.dropna(subset=['Description'], inplace=True)
        full_news_df.to_csv(f"{save_folder}/news_data.csv", index=False)
    return full_news_df

def aggregate_news_data(is_trending=True, days=3, save_folder = None):
    full_news_df = pd.DataFrame()
    since_date = int((datetime.now() - pd.DateOffset(days=days)).timestamp())
    
    if is_trending:
        trending_topics_df = search_news_for_trending_topics(since_date)
        full_news_df = pd.concat([full_news_df, trending_topics_df])
        
    for category in CATEGORIES:
        news_by_category_df = extract_news_by_category(category=category, since = since_date)
        full_news_df = pd.concat([full_news_df, news_by_category_df])
        
    
    for query in QUERIES:
        search_news_df = search_news(query=query, since=since_date)
        full_news_df = pd.concat([full_news_df, search_news_df])

    full_news_df = full_news_df.drop_duplicates(subset=['URL'])
    if save_folder:
        os.makedirs(save_folder, exist_ok=True)
        full_news_df.dropna(subset=['Description'], inplace=True)
        full_news_df.to_csv(f"{save_folder}/news_data.csv", index=False)
    return full_news_df