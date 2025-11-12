"""© 2025 University of Aberdeen. All rights reserved"""

import os
import requests
from pathlib import Path
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any

from pandas import DataFrame
from valyu import Valyu, SearchResponse
from valyu.types import SearchResult

from risklive.config import (VALYU_API_KEY, CATEGORIES, QUERIES,
                             EXCLUDED_SOURCES, TRENDING)

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

TODAY = datetime.today().date()

# ---- sequential compound search ----

def _row(response: SearchResponse) -> Dict[str, Any]:
    row: Dict[str, Any] = {}
    for result in response.results:
        for field in result.model_fields_set:
            row[field] = getattr(result, field, None)
        row["query"] = response.query
    return row

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


    def search(self,
               s: str,
               start_date: str,
               end_date: str | None = TODAY,
               market: str | None = "en_GB") -> SearchResponse | None:
        resp: SearchResponse | None = self.client.search(
            s,
            search_type="web",
            start_date=start_date,
            end_date=end_date,
            max_num_results=20,
            excluded_sources=EXCLUDED_SOURCES,
            relevance_threshold=0.5,
            response_length="short",
            max_price=40,
            country_code=market
        )
        return resp

    def compound_search(self,
                        searches: list[str],
                        start_date: str | None = None,
                        end_date: str | None = None,
                        market: str | None = None) -> List[Dict[str , Any]]:

        responses: list[Dict[str , Any]] = list()
        for s in searches:
            resp: SearchResponse | None = self.search(s, start_date, end_date, market)
            responses.append(_row(resp))
        return responses


    def compound_search_from_txt(
            self,
            start_date: str | None = None,
            end_date: str | None = None,
            country_code: str | None = None,
            search_type: str = "web",
            out_dir: str = "data",
            out_format: str = "csv",  # csv | jsonl | parquet
    ) -> DataFrame:

        # searches = ["nuclear", "nuclear power"]
        searches: list[str] = QUERIES + CATEGORIES
        responses = self.compound_search(searches, start_date, end_date)

        df : DataFrame = pd.DataFrame(responses).drop_duplicates(subset="url",
                                                                 keep="first").drop_duplicates(subset="url",keep="first")
        self.write_df(df, out_dir, out_format)
        return df

    def get_trending_topics(self,
                            start_date,
                            end_date=TODAY,
                            market="en-GB") -> List[Dict[str , Any]]:
        """Gets trending topics for a given market."""
        return self.compound_search(TRENDING, start_date, end_date, market)

    def get_news_by_category(
            self,
            category: str,
            start_date: str | None = None,
            end_date: str | None = TODAY,
            market: str | None = None
    ) -> List[Dict[str , Any]]:
        return self.compound_search(category, start_date, end_date, market)






api = ValyuAPI()
path = api.compound_search_from_txt(
    start_date="2025-11-03",
    end_date="2025-11-10",
    search_type="web",
    out_dir="data",
    out_format="csv",
)
print("Saved:", path)
