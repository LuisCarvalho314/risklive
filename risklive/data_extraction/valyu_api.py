"""© 2025 University of Aberdeen. All rights reserved"""

import os
import requests
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any
from itertools import chain
from typing import Iterable

from fontTools.misc.plistlib import end_date
from pandas import DataFrame
from valyu import Valyu, SearchResponse
from valyu.types import SearchResult

from risklive.config import (VALYU_API_KEY, CATEGORIES, QUERIES,
                             EXCLUDED_SOURCES, TRENDING, SAVE_DIR)

from pathlib import Path

CSV_DATA_DIR = Path(SAVE_DIR["CSV_DATA_DIR"])

import logging
logger = logging.getLogger(__name__)

EXT = {
    "csv": ".csv",
    "json": ".json",
    "jsonl": ".jsonl",
    "ndjson": ".ndjson",
    "parquet": ".parquet",
}

WRITERS = {
    "csv": lambda df, p, **kw: df.to_csv(p, index=False, **kw),
    "json": lambda df, p, **kw: df.to_json(p, orient="records",
                                           date_format="iso",
                                           force_ascii=False, indent=2,
                                           **kw),
    "jsonl": lambda df, p, **kw: df.to_json(p, orient="records",
                                            lines=True, date_format="iso",
                                            force_ascii=False, **kw),
    "ndjson": lambda df, p, **kw: df.to_json(p, orient="records",
                                             lines=True, date_format="iso",
                                             force_ascii=False, **kw),
    "parquet": lambda df, p, **kw: df.to_parquet(p, index=False, **kw),
}



# ---- sequential compound search ----

# def _rows_from_response(response: SearchResponse) -> list[Dict[str, Any]]:
#     rows: list[Dict[str, Any]] = []
#     for result in response.results:
#         # Pydantic model → dict
#         row = result.model_dump()
#         # attach originating query for traceability
#         row["query"] = response.query
#         rows.append(row)
#     return rows

def _rows_from_response(response: SearchResponse) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for result in response.results:
        data = result.model_dump()

        rows.append(
            {
                "Title": data.get("title"),
                "URL": data.get("url"),
                "Description": data.get("description"),
                "Timestamp": (datetime.now().isoformat()
                ),
                "Query": response.query,
            }
        )
    return rows


def write_df(
        df: pd.DataFrame,
        out: str | Path,
        out_format: str | None = None,
        filename_stem: str = "valyu",
        timestamp: bool = True,
        **kwargs,
) -> Path:
    out = Path(out)
    fmt = (out_format or out.suffix.lstrip(".") or "csv").lower()

    try:
        ext = EXT[fmt]
    except KeyError as e:
        raise ValueError(f"Unsupported format '{fmt}'. "
                         f"Choose from {', '.join(sorted(EXT))}") from e

    ts = f"_{datetime.now().strftime('%Y%m%d_%H%M%S')}" if (
            timestamp and not out.suffix) else ""
    filepath = out if out.suffix else out / f"{filename_stem}{ts}{ext}"
    filepath.parent.mkdir(parents=True, exist_ok=True)

    try:
        writer = WRITERS[fmt]
    except KeyError as e:
        raise ValueError(f"No writer for format '{fmt}'.") from e

    writer(df, str(filepath), **kwargs)
    return filepath

class ValyuAPI:

    def __init__(self, api_key: str = None):
        self.client = Valyu(api_key or os.getenv("VALYU_API_KEY"))


    def search_news(self,
                    query: str,
                    start_date: str,
                    market: str | None = "en_GB") -> SearchResponse | None:
        end_date = str(datetime.today().date())

        if start_date and end_date:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")

            if start_dt > end_dt:
                print(f"Start date ({start_date}) is later than end date ({end_date})")

        resp: SearchResponse | None = self.client.search(
            query,
            search_type="news",
            start_date=str(start_date),
            end_date=str(end_date),
            max_num_results=100,
            url_only=True,
            excluded_sources=EXCLUDED_SOURCES,
            relevance_threshold=0.5,
            response_length="short",
            max_price=150,
            country_code=market
        )
        if resp.success:
            print(f"Retrieved {len(resp.results)} results.")
        else:
            print(resp.error if resp else "Unknown error")
        return resp

    def compound_search(
            self,
            queries: list[str],
            start_date: str,
            market: str | None = None,
    ) -> list[Dict[str, Any]]:
        all_rows: list[Dict[str, Any]] = []

        for query in queries:
            resp = self.search_news(
                query=query,
                start_date=start_date,
                market=market,
            )
            if not resp or not resp.success:
                continue

            all_rows.extend(_rows_from_response(resp))

        return all_rows



    def compound_search_from_txt(
            self,
            start_date: str | None = None,
            end_date: str | None = None,
            country_code: str | None = None,
            search_type: str = "web",
            out_dir: str | Path = CSV_DATA_DIR,
            out_format: str = "csv",
    ) -> DataFrame:

        searches = ["nuclear", "nuclear power"]
        # searches: list[str] = QUERIES + CATEGORIES + TRENDING

        rows: list[Dict[str, Any]] = self.compound_search(
            searches,
            start_date=start_date,
            end_date=end_date,
            market=country_code,
        )

        df: DataFrame = pd.DataFrame.from_records(rows).drop_duplicates(
            subset="url",
            keep="first",
        )

        path = write_df(df, out_dir, out_format, filename_stem="news_data", timestamp=False)

        return path

    def get_trending_topics(self,
                            start_date,
                            end_date,
                            market="en-GB") -> List[Dict[str , Any]]:
        """Gets trending topics for a given market."""
        return self.compound_search(TRENDING, start_date, end_date, market)

    def get_news_by_category(
            self,
            category: str,
            since: int = 3,
            market: str | None = None
    ) -> List[Dict[str , Any]]:
        return self.compound_search(category, since, market)


def compound_search_news(queries: list[str], start_date: str) -> pd.DataFrame:
    valyu_api = ValyuAPI()

    rows: list[Dict[str, Any]] = valyu_api.compound_search(
        queries,
        start_date=start_date,
    )

    df: DataFrame = pd.DataFrame.from_records(rows).drop_duplicates(
        subset="URL",
        keep="first",
    )
    return df


def aggregate_regular_news(hours=1, save_folder=None):
    if save_folder and os.path.exists(f"{save_folder}/news_data.csv"):
        full_news_df = pd.read_csv(f"{save_folder}/news_data.csv")
    else:
        full_news_df = pd.DataFrame()
    start_date = (pd.Timestamp.now() - pd.DateOffset(hours=hours)).strftime(
        "%Y-%m-%d")

    queries: list[str] = CATEGORIES + QUERIES
    search_news_df = compound_search_news(queries, start_date)
    full_news_df = pd.concat([full_news_df, search_news_df]).drop_duplicates(subset=['URL'], keep='first')

    full_news_df.dropna(subset=['Description'], inplace=True)
    if save_folder:
        os.makedirs(save_folder, exist_ok=True)
        full_news_df.dropna(subset=['Description'], inplace=True)
        full_news_df.to_csv(f"{save_folder}/news_data.csv", index=False)
    return full_news_df


def aggregate_news_data(is_trending=True, days=3, save_folder=None):
    full_news_df = pd.DataFrame()
    since_date = (pd.Timestamp.now() - pd.DateOffset(days=days)).strftime(
        "%Y-%m-%d")

    queries: list[str] = CATEGORIES + QUERIES
    full_news_df = compound_search_news(queries, since = days)

    search_news_df = compound_search_news(queries, since_date)
    full_news_df = pd.concat([full_news_df, search_news_df]).drop_duplicates(subset=['URL'], keep='first')

    if save_folder:
        os.makedirs(save_folder, exist_ok=True)
        full_news_df.dropna(subset=['Description'], inplace=True)
        full_news_df.to_csv(f"{save_folder}/news_data.csv", index=False)
    return full_news_df


if __name__ == "__main__":
    print(VALYU_API_KEY)
    # aggregate_news_data(save_folder=CSV_DATA_DIR)
