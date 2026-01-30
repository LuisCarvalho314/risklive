from __future__ import annotations

import argparse
import logging
import re
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qsl, urlsplit, urlunsplit

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from scipy.optimize import LinearConstraint, milp
from scipy.sparse import csr_matrix, hstack, identity

# =============================================================================
# GLOBAL CONSTANTS
# =============================================================================

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gclid", "fbclid", "igshid", "mc_cid", "mc_eid", "ref", "ref_src", "spm",
}

RELEVANCE_POSITIVE = {"yes", "y", "true", "1"}
ALERT_RED_VALUES = {"red"}

VALYU_REQUIRED_COLUMNS = {"retrieved_at_utc", "url", "title", "query", "price"}
LLM_REQUIRED_COLUMNS = {"Timestamp", "Title", "Query", "Relevance", "AlertFlag", "LLM_Price"}
LLM_URL_CANDIDATES = ["url", "URL", "Url"]


# =============================================================================
# LOGGING
# =============================================================================

logger = logging.getLogger(__name__)


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


# =============================================================================
# UTILS
# =============================================================================

def ensure_columns_present(dataframe: pl.DataFrame, required: set[str], label: str) -> None:
    missing = required - set(dataframe.columns)
    if missing:
        raise ValueError(f"{label} missing required columns: {sorted(missing)}")


def safe_float_sum(series: Optional[pl.Series]) -> float:
    if series is None or series.len() == 0:
        return 0.0
    return float(series.cast(pl.Float64, strict=False).drop_nulls().sum() or 0.0)


def safe_rate(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def dataframe_to_markdown_table(dataframe: pl.DataFrame, max_rows: int = 40) -> str:
    if dataframe.height == 0:
        return "_(empty)_"
    view = dataframe.head(max_rows)
    columns = view.columns
    rows = view.to_dicts()

    def fmt(value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, float):
            return f"{value:.6g}"
        return str(value)

    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join(["---"] * len(columns)) + " |"
    body = "\n".join("| " + " | ".join(fmt(row.get(col)) for col in columns) + " |" for row in rows)
    suffix = ""
    if dataframe.height > max_rows:
        suffix = f"\n\n_(showing {max_rows} of {dataframe.height} rows)_"
    return "\n".join([header, sep, body]) + suffix


# =============================================================================
# NORMALIZATION
# =============================================================================

class Normalizer:
    @staticmethod
    def normalize_url(url: Optional[str]) -> Optional[str]:
        if not url:
            return None
        try:
            parts = urlsplit(url)
            scheme = parts.scheme.lower() if parts.scheme else "http"
            netloc = parts.netloc.lower()

            if netloc.endswith(":80") and scheme == "http":
                netloc = netloc[:-3]
            if netloc.endswith(":443") and scheme == "https":
                netloc = netloc[:-4]

            path = parts.path or "/"
            query_items = [
                (key, value)
                for key, value in parse_qsl(parts.query, keep_blank_values=True)
                if key not in TRACKING_PARAMS
            ]
            query_str = "&".join([f"{key}={value}" for key, value in query_items]) if query_items else ""
            return urlunsplit((scheme, netloc, path, query_str, ""))
        except Exception:
            return url

    @staticmethod
    def normalize_text(text: Optional[str]) -> Optional[str]:
        if not text:
            return None
        tokens = re.findall(r"[a-z0-9]+", str(text).lower())
        return " ".join(tokens) if tokens else None


# =============================================================================
# CONFIG + SCENARIOS
# =============================================================================

class LlmPricingMode(str, Enum):
    PER_ARTICLE = "per_article"     # variable cost based on covered articles
    FIXED_ANNUAL = "fixed_annual"   # fixed contract £/year (constant)


@dataclass(frozen=True)
class LlmPricing:
    mode: LlmPricingMode
    fixed_annual_cost_gbp: float = 0.0

    def is_fixed(self) -> bool:
        return self.mode == LlmPricingMode.FIXED_ANNUAL


@dataclass(frozen=True)
class PipelineInputs:
    valyu_csv_path: Path
    llm_csv_path: Path


@dataclass(frozen=True)
class ScenarioConfig:
    """
    Scenario = pricing model + output namespace.
    """
    name: str
    llm_pricing: LlmPricing


@dataclass(frozen=True)
class SweepConfig:
    coverage_levels: list[float]
    ilp_time_limit_seconds: int


@dataclass(frozen=True)
class OutputConfig:
    root_output_dir: Path

    def scenario_dir(self, scenario_name: str) -> Path:
        return self.root_output_dir / scenario_name

    def plots_dir(self, scenario_name: str) -> Path:
        return self.scenario_dir(scenario_name) / "plots"

    def report_path(self, scenario_name: str) -> Path:
        return self.scenario_dir(scenario_name) / "report.md"


@dataclass(frozen=True)
class TimeConfig:
    tolerance: timedelta


@dataclass(frozen=True)
class AnnualisationConfig:
    year_days: float = 365.2425


@dataclass(frozen=True)
class PipelineConfig:
    inputs: PipelineInputs
    outputs: OutputConfig
    time: TimeConfig
    sweep: SweepConfig
    annualisation: AnnualisationConfig
    scenarios: list[ScenarioConfig]


# =============================================================================
# DOMAIN TYPES
# =============================================================================

@dataclass(frozen=True)
class TimeWindow:
    valyu_time_min: Any
    valyu_time_max: Any
    llm_time_min: Any
    llm_time_max: Any
    window_days: float


@dataclass(frozen=True)
class Annualisation:
    window_days: float
    year_days: float
    factor_to_year: float


@dataclass(frozen=True)
class BaselineCosts:
    valyu_cost_window: float
    llm_cost_window: float
    total_cost_window: float

    valyu_cost_year: float
    llm_cost_year: float
    total_cost_year: float

    raw_rows: int
    unique_articles: int


@dataclass(frozen=True)
class ContradictionStats:
    article_count: int
    relevance_conflict_rate: float
    alert_conflict_rate: float
    red_not_relevant_rate: float


@dataclass(frozen=True)
class IlpStructures:
    queries: list[str]
    articles: list[str]
    article_by_query_matrix: csr_matrix
    target_mask: np.ndarray
    valyu_cost_per_query: np.ndarray
    llm_cost_per_article: np.ndarray  # zeros if scenario is fixed annual


@dataclass(frozen=True)
class IlpSolution:
    selected_query_indices: list[int]
    query_selection_vector: np.ndarray
    article_covered_vector: np.ndarray
    objective_value: float
    target_required: int
    target_total: int
    target_covered: int


@dataclass(frozen=True)
class ResultRow:
    scenario: str
    analysis: str
    objective: str

    coverage_target_pct: float
    coverage_achieved_pct: float
    selected_query_count: int
    selected_queries: list[str]

    valyu_cost_window: float
    llm_cost_window: float
    total_cost_window: float

    valyu_cost_year: float
    llm_cost_year: float
    total_cost_year: float

    valyu_savings_year: float
    llm_savings_year: float
    total_savings_year: float

    valyu_savings_rate: float
    llm_savings_rate: float
    total_savings_rate: float


# =============================================================================
# DATA LOADING + PREP
# =============================================================================

class InputLoader:
    def __init__(self, inputs: PipelineInputs) -> None:
        self.inputs = inputs

    def load(self) -> tuple[pl.DataFrame, pl.DataFrame, str]:
        valyu_dataframe = pl.read_csv(self.inputs.valyu_csv_path)
        llm_dataframe = pl.read_csv(self.inputs.llm_csv_path)

        logger.info("LOAD | valyu rows=%d cols=%d", valyu_dataframe.height, len(valyu_dataframe.columns))
        logger.info("LOAD | llm   rows=%d cols=%d", llm_dataframe.height, len(llm_dataframe.columns))

        ensure_columns_present(valyu_dataframe, VALYU_REQUIRED_COLUMNS, "valyu")
        ensure_columns_present(llm_dataframe, LLM_REQUIRED_COLUMNS, "llm")

        llm_url_col = next((c for c in LLM_URL_CANDIDATES if c in llm_dataframe.columns), None)
        if llm_url_col is None:
            raise ValueError(f"llm missing URL column; expected one of {LLM_URL_CANDIDATES}")

        logger.info("LOAD | LLM URL column: %s", llm_url_col)
        return valyu_dataframe, llm_dataframe, llm_url_col


class DataPreprocessor:
    def __init__(self) -> None:
        self.normalizer = Normalizer()

    def add_normalized_columns(
        self,
        valyu_dataframe: pl.DataFrame,
        llm_dataframe: pl.DataFrame,
        llm_url_col: str,
    ) -> tuple[pl.DataFrame, pl.DataFrame]:
        valyu_dataframe = valyu_dataframe.with_columns(
            pl.col("retrieved_at_utc").str.to_datetime(time_zone="UTC", strict=False).alias("valyu_ts")
        )
        llm_dataframe = llm_dataframe.with_columns(
            pl.col("Timestamp").str.to_datetime(time_zone="UTC", strict=False).alias("llm_ts")
        )

        valyu_dataframe = valyu_dataframe.with_columns([
            pl.col("url").map_elements(self.normalizer.normalize_url, return_dtype=pl.Utf8).alias("norm_url"),
            pl.col("title").map_elements(self.normalizer.normalize_text, return_dtype=pl.Utf8).alias("norm_title"),
            pl.col("query").map_elements(self.normalizer.normalize_text, return_dtype=pl.Utf8).alias("norm_query"),
            pl.col("price").cast(pl.Float64, strict=False).fill_null(0.0).alias("valyu_price_float"),
        ])

        llm_dataframe = llm_dataframe.with_columns([
            pl.col(llm_url_col).map_elements(self.normalizer.normalize_url, return_dtype=pl.Utf8).alias("norm_url"),
            pl.col("Title").map_elements(self.normalizer.normalize_text, return_dtype=pl.Utf8).alias("norm_title"),
            pl.col("Query").map_elements(self.normalizer.normalize_text, return_dtype=pl.Utf8).alias("norm_query"),
            pl.col("LLM_Price").cast(pl.Float64, strict=False).fill_null(0.0).alias("llm_price_float"),
        ])

        llm_dataframe = llm_dataframe.with_columns([
            pl.col("Relevance")
            .cast(pl.Utf8, strict=False)
            .str.to_lowercase()
            .map_elements(lambda s: (s in RELEVANCE_POSITIVE) if s is not None else False, return_dtype=pl.Boolean)
            .alias("is_relevant"),
            pl.col("AlertFlag")
            .cast(pl.Utf8, strict=False)
            .str.to_lowercase()
            .map_elements(lambda s: (s in ALERT_RED_VALUES) if s is not None else False, return_dtype=pl.Boolean)
            .alias("is_red"),
        ])

        valyu_ts_nulls = int(valyu_dataframe.select(pl.col("valyu_ts").null_count()).item())
        llm_ts_nulls = int(llm_dataframe.select(pl.col("llm_ts").null_count()).item())
        if valyu_ts_nulls != 0 or llm_ts_nulls != 0:
            logger.warning("NORMALIZE | timestamp nulls: valyu_ts=%d llm_ts=%d", valyu_ts_nulls, llm_ts_nulls)

        return valyu_dataframe, llm_dataframe

    def add_article_key(self, valyu_dataframe: pl.DataFrame, llm_dataframe: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
        if "duplicate_key" in valyu_dataframe.columns:
            valyu_dataframe = valyu_dataframe.with_columns(
                pl.coalesce([
                    pl.col("duplicate_key").cast(pl.Utf8, strict=False),
                    pl.col("norm_url"),
                    pl.col("norm_title"),
                ]).alias("article_key")
            )
        else:
            valyu_dataframe = valyu_dataframe.with_columns(
                pl.coalesce([pl.col("norm_url"), pl.col("norm_title")]).alias("article_key")
            )

        llm_dataframe = llm_dataframe.with_columns(
            pl.coalesce([pl.col("norm_url"), pl.col("norm_title")]).alias("article_key")
        )

        valyu_key_nulls = int(valyu_dataframe.select(pl.col("article_key").null_count()).item())
        llm_key_nulls = int(llm_dataframe.select(pl.col("article_key").null_count()).item())
        if valyu_key_nulls != 0 or llm_key_nulls != 0:
            raise ValueError(f"article_key contains nulls: valyu={valyu_key_nulls} llm={llm_key_nulls}")

        return valyu_dataframe, llm_dataframe


class WindowBuilder:
    def __init__(self, time_config: TimeConfig) -> None:
        self.time_config = time_config

    def compute(self, valyu_dataframe: pl.DataFrame) -> TimeWindow:
        valyu_time_min, valyu_time_max = valyu_dataframe.select(
            pl.col("valyu_ts").min().alias("time_min"),
            pl.col("valyu_ts").max().alias("time_max"),
        ).row(0)

        llm_time_min = valyu_time_min - self.time_config.tolerance
        llm_time_max = valyu_time_max + self.time_config.tolerance

        window_days = (valyu_time_max - valyu_time_min).total_seconds() / 86400.0
        window_days = max(float(window_days), 1e-9)

        logger.info("WINDOW | valyu: %s -> %s", valyu_time_min, valyu_time_max)
        logger.info("WINDOW | llm:   %s -> %s", llm_time_min, llm_time_max)
        logger.info("WINDOW | days:  %.6f", window_days)

        return TimeWindow(
            valyu_time_min=valyu_time_min,
            valyu_time_max=valyu_time_max,
            llm_time_min=llm_time_min,
            llm_time_max=llm_time_max,
            window_days=window_days,
        )

    @staticmethod
    def filter_valyu(valyu_dataframe: pl.DataFrame, time_window: TimeWindow) -> pl.DataFrame:
        return valyu_dataframe.filter(
            pl.col("valyu_ts").is_between(time_window.valyu_time_min, time_window.valyu_time_max, closed="both")
        )

    @staticmethod
    def filter_llm(llm_dataframe: pl.DataFrame, time_window: TimeWindow) -> pl.DataFrame:
        llm_window = llm_dataframe.filter(
            pl.col("llm_ts").is_between(time_window.llm_time_min, time_window.llm_time_max, closed="both")
        )
        logger.info("WINDOW | llm_window rows=%d", llm_window.height)
        return llm_window


class Annualiser:
    def __init__(self, annualisation_config: AnnualisationConfig) -> None:
        self.annualisation_config = annualisation_config

    def compute(self, window_days: float) -> Annualisation:
        factor_to_year = self.annualisation_config.year_days / max(window_days, 1e-12)
        return Annualisation(
            window_days=window_days,
            year_days=self.annualisation_config.year_days,
            factor_to_year=float(factor_to_year),
        )


# =============================================================================
# DERIVED DATASETS (DEDUP + EDGES)
# =============================================================================

class ArticleModelBuilder:
    @staticmethod
    def dedupe_llm_articles(llm_window: pl.DataFrame) -> pl.DataFrame:
        return (
            llm_window
            .sort(by=[pl.col("llm_price_float").is_null(), "llm_ts"], descending=[False, False])
            .unique(subset=["article_key"], keep="first")
            .select(["article_key", "llm_ts", "is_relevant", "is_red", "llm_price_float"])
        )

    @staticmethod
    def build_article_query_edges(valyu_window: pl.DataFrame) -> pl.DataFrame:
        return (
            valyu_window
            .filter(pl.col("norm_query").is_not_null())
            .select(["article_key", "norm_query"])
            .unique(subset=["article_key", "norm_query"])
        )

    @staticmethod
    def attach_labels_to_edges(edges: pl.DataFrame, llm_articles: pl.DataFrame) -> pl.DataFrame:
        return (
            edges
            .join(llm_articles, on="article_key", how="left")
            .with_columns([
                pl.col("is_relevant").fill_null(False),
                pl.col("is_red").fill_null(False),
                pl.col("llm_price_float").fill_null(0.0),
            ])
        )


# =============================================================================
# BASELINE + CONTRADICTIONS
# =============================================================================

class BaselineCalculator:
    @staticmethod
    def compute(
        valyu_window: pl.DataFrame,
        llm_articles: pl.DataFrame,
        annual: Annualisation,
        llm_pricing: LlmPricing,
    ) -> BaselineCosts:
        valyu_cost_window = safe_float_sum(valyu_window.get_column("valyu_price_float"))
        valyu_cost_year = valyu_cost_window * annual.factor_to_year

        if llm_pricing.is_fixed():
            llm_cost_year = float(llm_pricing.fixed_annual_cost_gbp)
            llm_cost_window = llm_cost_year / annual.factor_to_year
        else:
            llm_cost_window = safe_float_sum(llm_articles.get_column("llm_price_float"))
            llm_cost_year = llm_cost_window * annual.factor_to_year

        total_cost_window = valyu_cost_window + llm_cost_window
        total_cost_year = valyu_cost_year + llm_cost_year

        unique_articles = int(valyu_window.select(pl.col("article_key").n_unique()).item())

        return BaselineCosts(
            valyu_cost_window=valyu_cost_window,
            llm_cost_window=llm_cost_window,
            total_cost_window=total_cost_window,
            valyu_cost_year=valyu_cost_year,
            llm_cost_year=llm_cost_year,
            total_cost_year=total_cost_year,
            raw_rows=valyu_window.height,
            unique_articles=unique_articles,
        )


class ContradictionCalculator:
    @staticmethod
    def compute(llm_window: pl.DataFrame) -> ContradictionStats:
        per_article = (
            llm_window
            .group_by("article_key")
            .agg([
                pl.col("Relevance").cast(pl.Utf8, strict=False).n_unique().alias("relevance_n_unique"),
                pl.col("AlertFlag").cast(pl.Utf8, strict=False).n_unique().alias("alert_n_unique"),
                pl.col("is_relevant").fill_null(False).any().alias("any_relevant"),
                pl.col("is_red").fill_null(False).any().alias("any_red"),
            ])
            .with_columns([
                (pl.col("relevance_n_unique") > 1).alias("relevance_conflict"),
                (pl.col("alert_n_unique") > 1).alias("alert_conflict"),
                (pl.col("any_red") & (~pl.col("any_relevant"))).alias("red_not_relevant"),
            ])
        )

        return ContradictionStats(
            article_count=per_article.height,
            relevance_conflict_rate=float(per_article.select(pl.col("relevance_conflict").mean()).item() or 0.0),
            alert_conflict_rate=float(per_article.select(pl.col("alert_conflict").mean()).item() or 0.0),
            red_not_relevant_rate=float(per_article.select(pl.col("red_not_relevant").mean()).item() or 0.0),
        )


# =============================================================================
# ILP BUILD + SOLVE
# =============================================================================

class IlpStructureBuilder:
    @staticmethod
    def build(
        *,
        valyu_window: pl.DataFrame,
        llm_articles: pl.DataFrame,
        edges_with_labels: pl.DataFrame,
        target_col: str,  # "is_red" or "is_relevant"
        llm_pricing: LlmPricing,
    ) -> IlpStructures:
        queries = (
            valyu_window
            .filter(pl.col("norm_query").is_not_null())
            .select("norm_query")
            .unique()
            .sort("norm_query")
            .get_column("norm_query")
            .to_list()
        )
        query_to_index = {query: i for i, query in enumerate(queries)}

        articles = (
            llm_articles
            .select("article_key")
            .unique()
            .sort("article_key")
            .get_column("article_key")
            .to_list()
        )
        article_to_index = {article: i for i, article in enumerate(articles)}

        valyu_cost_per_query = np.zeros(len(queries), dtype=float)
        valyu_query_costs = (
            valyu_window
            .filter(pl.col("norm_query").is_not_null())
            .group_by("norm_query")
            .agg(pl.col("valyu_price_float").sum().alias("valyu_cost_sum"))
        )
        for row in valyu_query_costs.to_dicts():
            query = row["norm_query"]
            if query in query_to_index:
                valyu_cost_per_query[query_to_index[query]] = float(row["valyu_cost_sum"] or 0.0)

        llm_cost_per_article = np.zeros(len(articles), dtype=float)
        if not llm_pricing.is_fixed():
            for row in llm_articles.select(["article_key", "llm_price_float"]).to_dicts():
                article = row["article_key"]
                if article in article_to_index:
                    llm_cost_per_article[article_to_index[article]] = float(row["llm_price_float"] or 0.0)

        target_mask = (
            llm_articles
            .select(["article_key", pl.col(target_col).cast(pl.Boolean).fill_null(False).alias("target")])
            .sort("article_key")
            .get_column("target")
            .to_numpy()
            .astype(bool)
        )

        edges = (
            edges_with_labels
            .select(["article_key", "norm_query"])
            .filter(pl.col("norm_query").is_not_null())
            .unique(subset=["article_key", "norm_query"])
            .to_dicts()
        )

        row_indices: list[int] = []
        col_indices: list[int] = []
        data_values: list[float] = []
        for edge in edges:
            article = edge["article_key"]
            query = edge["norm_query"]
            if article in article_to_index and query in query_to_index:
                row_indices.append(article_to_index[article])
                col_indices.append(query_to_index[query])
                data_values.append(1.0)

        article_by_query_matrix = csr_matrix(
            (data_values, (row_indices, col_indices)),
            shape=(len(articles), len(queries)),
        )

        if target_mask.any():
            target_rows = np.where(target_mask)[0]
            unreachable = np.array((article_by_query_matrix[target_rows].sum(axis=1) == 0)).reshape(-1)
            unreachable_count = int(unreachable.sum())
            if unreachable_count != 0:
                logger.warning("ILP | unreachable target articles=%d (caps coverage)", unreachable_count)
        else:
            logger.warning("ILP | target set is empty (%s)", target_col)

        return IlpStructures(
            queries=queries,
            articles=articles,
            article_by_query_matrix=article_by_query_matrix,
            target_mask=target_mask,
            valyu_cost_per_query=valyu_cost_per_query,
            llm_cost_per_article=llm_cost_per_article,
        )


class IlpSolver:
    def __init__(self, time_limit_seconds: int) -> None:
        self.time_limit_seconds = time_limit_seconds

    def solve_min_queries(self, structures: IlpStructures, coverage_fraction: float) -> IlpSolution:
        return self._solve(structures, coverage_fraction, objective="min_queries")

    def solve_min_cost(self, structures: IlpStructures, coverage_fraction: float) -> IlpSolution:
        return self._solve(structures, coverage_fraction, objective="min_cost")

    def _solve(self, structures: IlpStructures, coverage_fraction: float, objective: str) -> IlpSolution:
        article_by_query_matrix = structures.article_by_query_matrix
        target_mask = structures.target_mask
        n_articles, n_queries = article_by_query_matrix.shape

        target_total = int(target_mask.sum())
        if target_total == 0:
            raise RuntimeError("Target set is empty; cannot solve ILP.")
        target_required = int(np.ceil(coverage_fraction * target_total))

        variable_count = n_queries + n_articles
        lower_bounds = np.zeros(variable_count)
        upper_bounds = np.ones(variable_count)
        bounds = (lower_bounds, upper_bounds)
        integrality = np.ones(variable_count, dtype=int)

        objective_coefficients = np.zeros(variable_count)
        if objective == "min_queries":
            objective_coefficients[:n_queries] = 1.0
        elif objective == "min_cost":
            objective_coefficients[:n_queries] = structures.valyu_cost_per_query
            objective_coefficients[n_queries:] = structures.llm_cost_per_article
        else:
            raise ValueError(f"Unknown objective: {objective}")

        link_matrix = hstack([(-article_by_query_matrix).tocsr(), identity(n_articles, format="csr")], format="csr")
        link_constraint = LinearConstraint(
            link_matrix,
            lb=-np.inf * np.ones(n_articles),
            ub=np.zeros(n_articles),
        )

        target_vector = target_mask.astype(float)
        coverage_matrix = hstack([csr_matrix((1, n_queries)), csr_matrix(target_vector.reshape(1, -1))], format="csr")
        coverage_constraint = LinearConstraint(
            coverage_matrix,
            lb=np.array([float(target_required)]),
            ub=np.array([np.inf]),
        )

        result = milp(
            c=objective_coefficients,
            integrality=integrality,
            bounds=bounds,
            constraints=[link_constraint, coverage_constraint],
            options={"time_limit": self.time_limit_seconds},
        )
        if not result.success:
            raise RuntimeError(f"ILP({objective}) failed: status={result.status} msg={getattr(result,'message','')}")

        solution_vector = np.asarray(result.x, dtype=float)
        query_selection_vector = solution_vector[:n_queries]
        article_covered_vector = solution_vector[n_queries:]

        selected_query_indices = [i for i, v in enumerate(query_selection_vector) if v >= 0.5]
        covered_binary = article_covered_vector >= 0.5
        target_covered = int((covered_binary & target_mask).sum())

        return IlpSolution(
            selected_query_indices=selected_query_indices,
            query_selection_vector=query_selection_vector,
            article_covered_vector=article_covered_vector,
            objective_value=float(result.fun),
            target_required=target_required,
            target_total=target_total,
            target_covered=target_covered,
        )


# =============================================================================
# EVALUATION
# =============================================================================

class SolutionEvaluator:
    @staticmethod
    def evaluate(
        *,
        scenario: ScenarioConfig,
        analysis: str,
        objective: str,
        coverage_target: float,
        solution: IlpSolution,
        structures: IlpStructures,
        baseline: BaselineCosts,
        annual: Annualisation,
    ) -> ResultRow:
        selected_query_indices = solution.selected_query_indices
        selected_queries = [structures.queries[i] for i in selected_query_indices]

        valyu_cost_window = float(structures.valyu_cost_per_query[selected_query_indices].sum()) if selected_query_indices else 0.0

        if scenario.llm_pricing.is_fixed():
            llm_cost_window = baseline.llm_cost_window
        else:
            covered_binary = (solution.article_covered_vector >= 0.5).astype(int)
            llm_cost_window = float((structures.llm_cost_per_article * covered_binary).sum())

        total_cost_window = valyu_cost_window + llm_cost_window

        valyu_cost_year = valyu_cost_window * annual.factor_to_year
        llm_cost_year = baseline.llm_cost_year if scenario.llm_pricing.is_fixed() else (llm_cost_window * annual.factor_to_year)
        total_cost_year = valyu_cost_year + llm_cost_year

        valyu_savings_year = baseline.valyu_cost_year - valyu_cost_year
        llm_savings_year = 0.0 if scenario.llm_pricing.is_fixed() else (baseline.llm_cost_year - llm_cost_year)
        total_savings_year = baseline.total_cost_year - total_cost_year

        valyu_savings_rate = safe_rate(valyu_savings_year, baseline.valyu_cost_year)
        llm_savings_rate = 0.0 if scenario.llm_pricing.is_fixed() else safe_rate(llm_savings_year, baseline.llm_cost_year)
        total_savings_rate = safe_rate(total_savings_year, baseline.total_cost_year)

        coverage_achieved = safe_rate(solution.target_covered, solution.target_total)

        return ResultRow(
            scenario=scenario.name,
            analysis=analysis,
            objective=objective,
            coverage_target_pct=coverage_target * 100.0,
            coverage_achieved_pct=coverage_achieved * 100.0,
            selected_query_count=len(selected_query_indices),
            selected_queries=selected_queries,
            valyu_cost_window=valyu_cost_window,
            llm_cost_window=llm_cost_window,
            total_cost_window=total_cost_window,
            valyu_cost_year=valyu_cost_year,
            llm_cost_year=llm_cost_year,
            total_cost_year=total_cost_year,
            valyu_savings_year=valyu_savings_year,
            llm_savings_year=llm_savings_year,
            total_savings_year=total_savings_year,
            valyu_savings_rate=valyu_savings_rate,
            llm_savings_rate=llm_savings_rate,
            total_savings_rate=total_savings_rate,
        )


# =============================================================================
# OUTPUTS: CSV + PLOTS + REPORT
# =============================================================================

class ResultsWriter:
    def __init__(self, output_config: OutputConfig) -> None:
        self.output_config = output_config

    def write_results_csv(self, scenario_name: str, analysis: str, results: list[ResultRow]) -> Path:
        out_df = pl.DataFrame([{
            "scenario": r.scenario,
            "analysis": r.analysis,
            "objective": r.objective,
            "coverage_target_pct": r.coverage_target_pct,
            "coverage_achieved_pct": r.coverage_achieved_pct,
            "selected_query_count": r.selected_query_count,
            "valyu_cost_year": r.valyu_cost_year,
            "llm_cost_year": r.llm_cost_year,
            "total_cost_year": r.total_cost_year,
            "valyu_savings_year": r.valyu_savings_year,
            "llm_savings_year": r.llm_savings_year,
            "total_savings_year": r.total_savings_year,
            "valyu_savings_rate_pct": r.valyu_savings_rate * 100.0,
            "llm_savings_rate_pct": r.llm_savings_rate * 100.0,
            "total_savings_rate_pct": r.total_savings_rate * 100.0,
        } for r in results if r.scenario == scenario_name and r.analysis == analysis]).sort(["objective", "coverage_target_pct"])

        scenario_dir = self.output_config.scenario_dir(scenario_name)
        scenario_dir.mkdir(parents=True, exist_ok=True)
        out_path = scenario_dir / f"ilp_results_{analysis.lower()}.csv"
        out_df.write_csv(out_path)
        logger.info("WROTE | %s", out_path)
        return out_path


class Plotter:
    def __init__(self, output_config: OutputConfig) -> None:
        self.output_config = output_config

    def plot(self, scenario_name: str, analysis: str, rows: list[ResultRow], baseline: BaselineCosts) -> None:
        scenario_plots_dir = self.output_config.plots_dir(scenario_name)
        scenario_plots_dir.mkdir(parents=True, exist_ok=True)

        rows = sorted(rows, key=lambda r: (r.objective, r.coverage_target_pct))
        by_objective: dict[str, list[ResultRow]] = {}
        for row in rows:
            by_objective.setdefault(row.objective, []).append(row)

        colors = {
            "total": "#000000",
            "valyu": "#ff7f0e",
            "llm": "#2ca02c",
            "queries": "#1f77b4",
            "savings": "#17becf",
            "rate_total": "#111111",
            "rate_valyu": "#ff7f0e",
            "rate_llm": "#2ca02c",
        }

        baseline_total = baseline.total_cost_year
        baseline_valyu = baseline.valyu_cost_year
        baseline_llm = baseline.llm_cost_year

        for objective, objective_rows in by_objective.items():
            x_values = [r.coverage_target_pct for r in objective_rows]

            total_cost = [r.total_cost_year for r in objective_rows]
            valyu_cost = [r.valyu_cost_year for r in objective_rows]
            llm_cost = [r.llm_cost_year for r in objective_rows]
            query_counts = [r.selected_query_count for r in objective_rows]

            total_savings = [r.total_savings_year for r in objective_rows]
            valyu_savings = [r.valyu_savings_year for r in objective_rows]
            llm_savings = [r.llm_savings_year for r in objective_rows]

            total_rate = [r.total_savings_rate * 100.0 for r in objective_rows]
            valyu_rate = [r.valyu_savings_rate * 100.0 for r in objective_rows]
            llm_rate = [r.llm_savings_rate * 100.0 for r in objective_rows]

            # 1) Annualised cost vs coverage + baseline lines
            plt.figure(figsize=(9, 5.5))
            plt.plot(x_values, total_cost, marker="o", color=colors["total"], label="Total cost (£/yr)")
            plt.plot(x_values, valyu_cost, marker="o", color=colors["valyu"], label="Valyu cost (£/yr)")
            plt.plot(x_values, llm_cost, marker="o", color=colors["llm"], label="LLM cost (£/yr)")

            plt.axhline(baseline_total, color=colors["total"], linestyle="--", linewidth=1,
                        label=f"Baseline total (£/yr) = {baseline_total:.2f}")
            plt.axhline(baseline_valyu, color=colors["valyu"], linestyle="--", linewidth=1,
                        label=f"Baseline Valyu (£/yr) = {baseline_valyu:.2f}")
            plt.axhline(baseline_llm, color=colors["llm"], linestyle="--", linewidth=1,
                        label=f"Baseline LLM (£/yr) = {baseline_llm:.2f}")

            plt.xlabel("Coverage target (%)")
            plt.ylabel("Annualised cost (£/year)")
            plt.title(f"{scenario_name} — {analysis} — {objective}: Annualised Cost vs Coverage")
            plt.grid(True, alpha=0.25)
            plt.legend()
            plt.tight_layout()
            plt.savefig(scenario_plots_dir / f"{analysis.lower()}_{objective}_annual_cost.png", dpi=170)
            plt.close()

            # 2) Query count vs coverage
            plt.figure(figsize=(9, 5.5))
            plt.plot(x_values, query_counts, marker="o", color=colors["queries"], label="# queries")
            plt.xlabel("Coverage target (%)")
            plt.ylabel("Number of queries")
            plt.title(f"{scenario_name} — {analysis} — {objective}: Query Count vs Coverage")
            plt.grid(True, alpha=0.25)
            plt.legend()
            plt.tight_layout()
            plt.savefig(scenario_plots_dir / f"{analysis.lower()}_{objective}_query_count.png", dpi=170)
            plt.close()

            # 3) Annualised savings vs coverage
            plt.figure(figsize=(9, 5.5))
            plt.plot(x_values, total_savings, marker="o", color=colors["savings"], label="Total savings (£/yr)")
            plt.plot(x_values, valyu_savings, marker="o", color=colors["valyu"], label="Valyu savings (£/yr)")
            plt.plot(x_values, llm_savings, marker="o", color=colors["llm"], label="LLM savings (£/yr)")
            plt.axhline(0.0, color="#666666", linewidth=1)
            plt.xlabel("Coverage target (%)")
            plt.ylabel("Annualised savings (£/year)")
            plt.title(f"{scenario_name} — {analysis} — {objective}: Annualised Savings vs Coverage (vs baseline)")
            plt.grid(True, alpha=0.25)
            plt.legend()
            plt.tight_layout()
            plt.savefig(scenario_plots_dir / f"{analysis.lower()}_{objective}_annual_savings.png", dpi=170)
            plt.close()

            # 4) Savings rates vs coverage
            plt.figure(figsize=(9, 5.5))
            plt.plot(x_values, total_rate, marker="o", color=colors["rate_total"], label="Total savings rate (% of total baseline)")
            plt.plot(x_values, valyu_rate, marker="o", color=colors["rate_valyu"], label="Valyu savings rate (% of Valyu baseline)")
            plt.plot(x_values, llm_rate, marker="o", color=colors["rate_llm"], label="LLM savings rate (% of LLM baseline)")
            plt.axhline(0.0, color="#666666", linewidth=1)
            plt.xlabel("Coverage target (%)")
            plt.ylabel("Savings rate (% of baseline)")
            plt.title(f"{scenario_name} — {analysis} — {objective}: Savings Rates vs Coverage")
            plt.grid(True, alpha=0.25)
            plt.legend()
            plt.tight_layout()
            plt.savefig(scenario_plots_dir / f"{analysis.lower()}_{objective}_savings_rates.png", dpi=170)
            plt.close()


class ReportWriter:
    def __init__(self, output_config: OutputConfig) -> None:
        self.output_config = output_config

    @staticmethod
    def _format_query_list_for_table(queries: list[str], per_line: int = 6) -> str:
        # Use <br> so markdown tables stay readable.
        if not queries:
            return ""
        chunks = [queries[i:i + per_line] for i in range(0, len(queries), per_line)]
        return "<br>".join([", ".join(chunk) for chunk in chunks])

    def write(
        self,
        *,
        scenario: ScenarioConfig,
        time_window: TimeWindow,
        baseline: BaselineCosts,
        contradictions: ContradictionStats,
        results: list[ResultRow],
    ) -> Path:
        scenario_dir = self.output_config.scenario_dir(scenario.name)
        scenario_dir.mkdir(parents=True, exist_ok=True)

        scenario_results = [r for r in results if r.scenario == scenario.name]

        results_df = pl.DataFrame([{
            "analysis": r.analysis,
            "objective": r.objective,
            "coverage_target_pct": round(r.coverage_target_pct, 2),
            "coverage_achieved_pct": round(r.coverage_achieved_pct, 2),
            "selected_query_count": r.selected_query_count,
            "valyu_cost_year": r.valyu_cost_year,
            "llm_cost_year": r.llm_cost_year,
            "total_cost_year": r.total_cost_year,
            "valyu_savings_year": r.valyu_savings_year,
            "llm_savings_year": r.llm_savings_year,
            "total_savings_year": r.total_savings_year,
            "valyu_savings_rate_pct": r.valyu_savings_rate * 100.0,
            "llm_savings_rate_pct": r.llm_savings_rate * 100.0,
            "total_savings_rate_pct": r.total_savings_rate * 100.0,
        } for r in scenario_results]).sort(["analysis", "objective", "coverage_target_pct"])

        group_keys = ["analysis", "objective", "coverage_target_pct"]
        best_per_cov = (
            results_df
            .sort(group_keys + ["total_cost_year"])
            .group_by(group_keys, maintain_order=True)
            .first()
            .sort(group_keys)
        )

        # 100% coverage query sets (target==100)
        hundred_rows = [r for r in scenario_results if abs(r.coverage_target_pct - 100.0) < 1e-9]
        hundred_df = pl.DataFrame([{
            "analysis": r.analysis,
            "objective": r.objective,
            "coverage_achieved_pct": round(r.coverage_achieved_pct, 2),
            "selected_query_count": r.selected_query_count,
            "selected_queries": self._format_query_list_for_table(r.selected_queries),
        } for r in sorted(hundred_rows, key=lambda x: (x.analysis, x.objective))]).sort(["analysis", "objective"])

        assumptions = [
            "Valyu cost is paid per raw returned row (duplicates still cost).",
            "Coverage is computed over deduped unique articles (article_key).",
            "LLM window is filtered to Valyu time window ± tolerance.",
            "Missing LLM_Price is treated as 0.0.",
        ]
        if scenario.llm_pricing.is_fixed():
            assumptions.append(
                f"LLM cost is fixed at £{scenario.llm_pricing.fixed_annual_cost_gbp:.2f} per year (contract); min_cost optimises Valyu only."
            )
        else:
            assumptions.append("LLM cost is paid per unique (deduped) article processed; min_cost includes Valyu + LLM.")

        lines: list[str] = []
        lines.append(f"# Query Set Optimization Report — Scenario: {scenario.name}\n")
        lines.append("## Time Window\n")
        lines.append(f"- Valyu window: {time_window.valyu_time_min} → {time_window.valyu_time_max}\n")
        lines.append(f"- LLM filter window (± tolerance): {time_window.llm_time_min} → {time_window.llm_time_max}\n")
        lines.append(f"- Window length (days): {time_window.window_days:.6f}\n")

        lines.append("## Assumptions\n")
        lines.extend([f"- {a}" for a in assumptions])
        lines.append("")

        lines.append("## Baseline Costs (Annualised)\n")
        lines.append(dataframe_to_markdown_table(pl.DataFrame([{
            "valyu_cost_year": baseline.valyu_cost_year,
            "llm_cost_year": baseline.llm_cost_year,
            "total_cost_year": baseline.total_cost_year,
            "raw_rows": baseline.raw_rows,
            "unique_articles": baseline.unique_articles,
        }]), max_rows=10))
        lines.append("")

        lines.append("## LLM Label Contradiction Rates\n")
        lines.append(dataframe_to_markdown_table(pl.DataFrame([{
            "article_count_in_window": contradictions.article_count,
            "relevance_conflict_rate": contradictions.relevance_conflict_rate,
            "alert_conflict_rate": contradictions.alert_conflict_rate,
            "red_not_relevant_rate": contradictions.red_not_relevant_rate,
        }]), max_rows=10))
        lines.append("")

        lines.append("## 100% Coverage Query Sets\n")
        lines.append("Selected queries for coverage_target = 100% (one row per analysis × objective):\n")
        lines.append(dataframe_to_markdown_table(hundred_df, max_rows=50))
        lines.append("")

        lines.append("## ILP Results (Best per coverage target)\n")
        lines.append(dataframe_to_markdown_table(best_per_cov, max_rows=500))
        lines.append("")

        lines.append("## Outputs\n")
        lines.append(f"- CSVs: `{scenario.name}/ilp_results_red.csv`, `{scenario.name}/ilp_results_relevant.csv`\n")
        lines.append(f"- Plots: `{scenario.name}/plots/`\n")

        report_path = self.output_config.report_path(scenario.name)
        report_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("WROTE | %s", report_path)
        return report_path


# =============================================================================
# PIPELINE RUNNER (MULTI-SCENARIO)
# =============================================================================

class QueryOptimisationRunner:
    """
    Loads/prepares data once, then runs multiple scenarios without recomputing heavy prep steps.
    """
    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        self.input_loader = InputLoader(config.inputs)
        self.preprocessor = DataPreprocessor()
        self.window_builder = WindowBuilder(config.time)
        self.annualiser = Annualiser(config.annualisation)
        self.ilp_solver = IlpSolver(time_limit_seconds=config.sweep.ilp_time_limit_seconds)

        self.results_writer = ResultsWriter(config.outputs)
        self.plotter = Plotter(config.outputs)
        self.report_writer = ReportWriter(config.outputs)

    def run(self) -> None:
        self.config.outputs.root_output_dir.mkdir(parents=True, exist_ok=True)

        # Shared load/prep (scenario-independent)
        valyu_df, llm_df, llm_url_col = self.input_loader.load()
        valyu_df, llm_df = self.preprocessor.add_normalized_columns(valyu_df, llm_df, llm_url_col)
        valyu_df, llm_df = self.preprocessor.add_article_key(valyu_df, llm_df)

        time_window = self.window_builder.compute(valyu_df)
        annual = self.annualiser.compute(time_window.window_days)

        valyu_window = self.window_builder.filter_valyu(valyu_df, time_window)
        llm_window = self.window_builder.filter_llm(llm_df, time_window)

        llm_articles = ArticleModelBuilder.dedupe_llm_articles(llm_window)
        edges = ArticleModelBuilder.build_article_query_edges(valyu_window)
        edges_with_labels = ArticleModelBuilder.attach_labels_to_edges(edges, llm_articles)

        contradictions = ContradictionCalculator.compute(llm_window)

        all_results: list[ResultRow] = []

        for scenario in self.config.scenarios:
            logger.info("SCENARIO | %s | llm_mode=%s fixed_annual=%.2f",
                        scenario.name, scenario.llm_pricing.mode.value, scenario.llm_pricing.fixed_annual_cost_gbp)

            baseline = BaselineCalculator.compute(valyu_window, llm_articles, annual, scenario.llm_pricing)
            logger.info("BASELINE | %s | Valyu £/yr=%.4f | LLM £/yr=%.4f | Total £/yr=%.4f",
                        scenario.name, baseline.valyu_cost_year, baseline.llm_cost_year, baseline.total_cost_year)

            for analysis, target_col in [("RED", "is_red"), ("RELEVANT", "is_relevant")]:
                logger.info("ILP | %s | %s", scenario.name, analysis)

                structures = IlpStructureBuilder.build(
                    valyu_window=valyu_window,
                    llm_articles=llm_articles,
                    edges_with_labels=edges_with_labels,
                    target_col=target_col,
                    llm_pricing=scenario.llm_pricing,
                )

                for coverage in self.config.sweep.coverage_levels:
                    solution_min_queries = self.ilp_solver.solve_min_queries(structures, coverage)
                    all_results.append(SolutionEvaluator.evaluate(
                        scenario=scenario,
                        analysis=analysis,
                        objective="min_queries",
                        coverage_target=coverage,
                        solution=solution_min_queries,
                        structures=structures,
                        baseline=baseline,
                        annual=annual,
                    ))

                    solution_min_cost = self.ilp_solver.solve_min_cost(structures, coverage)
                    all_results.append(SolutionEvaluator.evaluate(
                        scenario=scenario,
                        analysis=analysis,
                        objective="min_cost",
                        coverage_target=coverage,
                        solution=solution_min_cost,
                        structures=structures,
                        baseline=baseline,
                        annual=annual,
                    ))

                self.results_writer.write_results_csv(scenario.name, analysis, all_results)
                self.plotter.plot(
                    scenario_name=scenario.name,
                    analysis=analysis,
                    rows=[r for r in all_results if r.scenario == scenario.name and r.analysis == analysis],
                    baseline=baseline,
                )

            self.report_writer.write(
                scenario=scenario,
                time_window=time_window,
                baseline=baseline,
                contradictions=contradictions,
                results=all_results,
            )


# =============================================================================
# CLI
# =============================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ILP/MILP-based query set optimisation (RED + RELEVANT).")

    parser.add_argument("--valyu", type=Path, default=Path("analytics.csv"), help="Path to Valyu analytics CSV.")
    parser.add_argument("--llm", type=Path, default=Path("news_data_with_llm_info.csv"), help="Path to LLM CSV.")

    parser.add_argument("--out", type=Path, default=Path("results"), help="Root output directory (scenario subfolders).")

    parser.add_argument("--tolerance-hours", type=float, default=1.0, help="LLM window tolerance (hours).")

    parser.add_argument("--coverage-min", type=int, default=80, help="Minimum coverage percent (inclusive).")
    parser.add_argument("--coverage-max", type=int, default=100, help="Maximum coverage percent (inclusive).")

    parser.add_argument("--ilp-time-limit", type=int, default=20, help="MILP time limit seconds per solve.")

    parser.add_argument(
        "--scenarios",
        type=str,
        default="per_article",
        help="Comma-separated scenarios: per_article, fixed_annual, or both (e.g. per_article,fixed_annual).",
    )
    parser.add_argument(
        "--llm-fixed-annual",
        type=float,
        default=0.0,
        help="Fixed £/year for LLM contract (used for fixed_annual scenario).",
    )

    parser.add_argument("--log-level", type=str, default="INFO", help="Logging level (DEBUG/INFO/WARN/ERROR).")
    return parser.parse_args()


def build_scenarios(scenario_names_csv: str, fixed_annual_cost: float) -> list[ScenarioConfig]:
    requested = [s.strip().lower() for s in scenario_names_csv.split(",") if s.strip()]
    scenarios: list[ScenarioConfig] = []

    for name in requested:
        if name == "per_article":
            scenarios.append(ScenarioConfig(
                name="per_article",
                llm_pricing=LlmPricing(mode=LlmPricingMode.PER_ARTICLE),
            ))
        elif name == "fixed_annual":
            scenarios.append(ScenarioConfig(
                name="fixed_annual",
                llm_pricing=LlmPricing(mode=LlmPricingMode.FIXED_ANNUAL, fixed_annual_cost_gbp=float(fixed_annual_cost)),
            ))
        else:
            raise ValueError(f"Unknown scenario '{name}'. Valid: per_article, fixed_annual.")

    # de-dup while preserving order
    unique: list[ScenarioConfig] = []
    seen: set[str] = set()
    for scenario in scenarios:
        if scenario.name not in seen:
            unique.append(scenario)
            seen.add(scenario.name)
    return unique


def main() -> None:
    args = parse_args()
    configure_logging(args.log_level)

    coverage_levels = [c / 100.0 for c in range(int(args.coverage_min), int(args.coverage_max) + 1)]
    scenarios = build_scenarios(args.scenarios, float(args.llm_fixed_annual))

    config = PipelineConfig(
        inputs=PipelineInputs(valyu_csv_path=args.valyu, llm_csv_path=args.llm),
        outputs=OutputConfig(root_output_dir=args.out),
        time=TimeConfig(tolerance=timedelta(hours=float(args.tolerance_hours))),
        sweep=SweepConfig(coverage_levels=coverage_levels, ilp_time_limit_seconds=int(args.ilp_time_limit)),
        annualisation=AnnualisationConfig(),
        scenarios=scenarios,
    )

    runner = QueryOptimisationRunner(config)
    runner.run()


if __name__ == "__main__":
    main()
