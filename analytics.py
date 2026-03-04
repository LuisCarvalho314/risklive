import re
from urllib.parse import parse_qsl, urlsplit, urlunsplit
from datetime import timedelta
import polars as pl
import numpy as np
from scipy.optimize import LinearConstraint, milp
from scipy.sparse import csr_matrix
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


_TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_src",
    "spm",
}


def normalize_url(url: str | None) -> str | None:
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
        query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k not in _TRACKING_PARAMS]
        query_str = "&".join([f"{k}={v}" for k, v in query]) if query else ""
        return urlunsplit((scheme, netloc, path, query_str, ""))
    except Exception:
        return url


def title_jaccard(left: str | None, right: str | None) -> float | None:
    if not left or not right:
        return None
    left_tokens = set(re.findall(r"[a-z0-9]+", left.lower()))
    right_tokens = set(re.findall(r"[a-z0-9]+", right.lower()))
    if not left_tokens or not right_tokens:
        return None
    inter = left_tokens & right_tokens
    union = left_tokens | right_tokens
    return len(inter) / len(union)


def normalize_title(title: str | None) -> str | None:
    if not title:
        return None
    tokens = re.findall(r"[a-z0-9]+", title.lower())
    return " ".join(tokens) if tokens else None


valyu_df = pl.read_csv("analytics.csv")
llm_df = pl.read_csv("news_data_with_llm_info.csv").rename({"URL": "url"})

valyu_ts_col = "retrieved_at_utc"
llm_ts_col = "Timestamp"

# Normalize timestamps ---------------------------------------------------------

valyu_df = valyu_df.with_columns(
    pl.col(valyu_ts_col).str.to_datetime(time_zone="UTC", strict=False).alias("valyu_ts")
)
llm_df = llm_df.with_columns(
    pl.col(llm_ts_col).str.to_datetime(time_zone="UTC", strict=False).alias("llm_ts")
)


# Normalize URLs ---------------------------------------------------------------

valyu_df = valyu_df.with_columns(
    pl.col("url").map_elements(normalize_url, return_dtype=pl.Utf8).alias("norm_url")
)
llm_df = llm_df.with_columns(
    pl.col("url").map_elements(normalize_url, return_dtype=pl.Utf8).alias("norm_url")
)

# Normalize titles -------------------------------------------------------------

valyu_df = valyu_df.with_columns(
    pl.col("title").map_elements(normalize_title, return_dtype=pl.Utf8).alias("norm_title")
)
llm_df = llm_df.with_columns(
    pl.col("Title").map_elements(normalize_title, return_dtype=pl.Utf8).alias("norm_title")
)

# Normalize queries
# -------------------------------------------------------------

valyu_df = valyu_df.with_columns(
    pl.col("query").map_elements(normalize_title, return_dtype=pl.Utf8).alias(
        "norm_query")
)
llm_df = llm_df.with_columns(
    pl.col("Query").map_elements(normalize_title, return_dtype=pl.Utf8).alias(
        "norm_query")
)

# Compute bounds from raw_df (first dataframe)
time_min, time_max = valyu_df.select(
    pl.col("valyu_ts").min().alias("time_min"),
    pl.col("valyu_ts").max().alias("time_max"),
).row(0)

# add ±1 hour tolerance
tolerance = timedelta(hours=1)
time_min_tol = time_min - tolerance
time_max_tol = time_max + tolerance # (min, max) from raw_df

# Filter processed_df (second dataframe) using raw_df bounds
processed_df = llm_df.filter(
    pl.col("llm_ts").is_between(time_min_tol, time_max_tol, closed="both")
)

join_keys = ["norm_title", "norm_query"]

matched_df = valyu_df.join(processed_df, on=join_keys, how="left",
                         suffix="__proc")

matched_processed_only = matched_df.select(
    [pl.col(f"{c}__proc") for c in processed_df.columns if c not in join_keys]
)

# matched_processed_only = (
#     valyu_df
#     .join(processed_df, on=join_keys, how="left")
#     .select(pl.col(processed_df.columns))   # keeps only processed_df columns
# )

filtered = matched_processed_only.filter(pl.col("LLM_Response").is_not_null())
duplicates_matched_df = matched_df.filter(pl.col("LLM_Response").is_null())

key_cols = ["norm_url", "norm_title"]

with_rank = matched_processed_only.with_columns(
    pl.int_range(pl.len()).over(key_cols).alias("dup_index")  # 0,1,2... within each key group
)

deduped_first = with_rank.filter(pl.col("dup_index") == 0).drop("dup_index")
extras = with_rank.filter(pl.col("dup_index") > 0).drop("dup_index")



out_path = Path("matched_df.csv").resolve()
matched_df.write_csv(out_path)



# Analytics
num_duplicates = duplicates_matched_df.height


def extrapolate_price(df: pl.DataFrame, price_col: str, name: str):


    cost = df.select(
        pl.col(price_col).cast(pl.Float64, strict=False).sum()
    ).item()

    window_seconds = (time_max - time_min).total_seconds()
    window_days = window_seconds / 86400.0

    # average month/year lengths (Gregorian)
    avg_days_per_month = 365.2425 / 12.0  # 30.436875
    avg_days_per_year = 365.2425

    monthly_cost = cost * (
                avg_days_per_month / window_days) if window_days > 0 else None
    yearly_cost = cost * (
                avg_days_per_year / window_days) if window_days > 0 else None

    print(f"{name} window_days:", window_days)
    print(f"{name} number:", df.height)
    print(f"{name} cost:", cost)
    print(f"{name} monthly_cost_est:", monthly_cost)
    print(f"{name} yearly_cost_est:", yearly_cost)


extrapolate_price(duplicates_matched_df, "price", "Duplicate Searches")
extrapolate_price(extras, "LLM_Price", "Duplicate LLM Processed")

percentage_duplicates = (num_duplicates /
                         processed_df.height * 100)
print(f"Percentage of duplicates: {percentage_duplicates:.2f}%")


key_cols = ["norm_url", "norm_title"]
price_col = "LLM_Price"

matched_with_broadcast_price = matched_processed_only.with_columns(
    pl.coalesce(
        [
            pl.col(price_col),
            pl.col(price_col).drop_nulls().first().over(key_cols),  # first non-null in the set
        ]
    ).alias(price_col)
)

# (optional) verify how many still-null prices remain (sets with no non-null price at all)
still_null = matched_with_broadcast_price.filter(pl.col(price_col).is_null()).height
print("rows still null LLM_Price:", still_null)


import polars as pl

key_cols = ["norm_url", "norm_title"]
price_col = "LLM_Price"

no_price_groups = (
    matched_processed_only
    .group_by(key_cols)
    .agg([
        pl.len().alias("group_size"),
        pl.col(price_col).is_not_null().any().alias("group_has_price"),
    ])
    .filter(~pl.col("group_has_price"))
    .sort("group_size", descending=True)
)

print("groups with no price:", no_price_groups.height)
print(no_price_groups.head(20))


still_null_rows = matched_with_broadcast_price.filter(pl.col(price_col).is_null())
print("rows still null:", still_null_rows.height)
print(still_null_rows.select(key_cols + ["Query", "llm_ts"]).head(20))

#



# how many rows are fully-null (i.e., no match at all)?
all_null_rows = matched_processed_only.filter(
    pl.all_horizontal(pl.all().is_null())
).height
print("rows with no match (all processed cols null):", all_null_rows)

# how many LLM_Price are null overall?
print("LLM_Price null rows:", matched_processed_only.filter(pl.col("LLM_Price").is_null()).height)


print("LLM_Price dtype:", processed_df.schema.get("LLM_Price"))

print(
    processed_df.select(
        pl.len().alias("rows"),
        pl.col("LLM_Price").null_count().alias("llm_price_nulls"),
    )
)

# # joined = valyu_df.join(
# #     result,
# #     on="norm_url",
# #     how="left",
# # )
#
# #
# # result = pl.concat([valyu_df, llm_df],how="diagonal")
#
# total = valyu_df.height
# lost_pct = (total - result.height / total * 100) if total else 0.0
# print(f"Lost matches: {total - result.height}/{total} ({lost_pct:.2f}%)")
#
# # result = matched
#
# PLOTS_DIR = Path("results/plots")
# PLOTS_DIR.mkdir(parents=True, exist_ok=True)
#
# result_costs_all = result.with_columns(
#     [
#         pl.col("price").cast(pl.Float64, strict=False).fill_null(0.0).alias("valyu_cost"),
#         pl.col("LLM_Price").cast(pl.Float64, strict=False).fill_null(0.0).alias("llm_cost"),
#     ]
# ).with_columns(
#     pl.when(pl.col("llm_ts").is_not_null())
#     .then(pl.concat_str([pl.col("norm_url"), pl.col("llm_ts").cast(pl.Utf8)], separator="|"))
#     .otherwise(None)
#     .alias("llm_key")
# )
#
# time_start = result_costs_all.select(pl.col("valyu_ts").min()).item()
# time_end = result_costs_all.select(pl.col("valyu_ts").max()).item()
# timespan_days = None
# if time_start and time_end:
#     timespan_days = max((time_end - time_start).total_seconds() / 86400.0, 1e-9)
#
# def _costs_with_llm_cap(df: pl.DataFrame) -> tuple[float, float, float]:
#     valyu_sum = df.select(pl.col("valyu_cost").sum()).item()
#     llm_sum = (
#         df.filter(pl.col("llm_key").is_not_null())
#         .group_by("llm_key")
#         .agg(pl.col("llm_cost").first())
#         .select(pl.col("llm_cost").sum())
#         .item()
#     )
#     llm_sum = 0.0 if llm_sum is None else llm_sum
#     total = valyu_sum + llm_sum
#     return total, valyu_sum, llm_sum
#
#
# total_cost_all, valyu_cost_all, llm_cost_all = _costs_with_llm_cap(result_costs_all)
#
#
# def analyze_subset(analysis_df: pl.DataFrame, suffix: str, title: str) -> None:
#     analysis_df = analysis_df.with_columns(
#         pl.col("Query").cast(pl.Utf8, strict=False).alias("Query")
#     ).with_columns(
#         pl.col("Query").str.len_chars().alias("query_len")
#     )
#
#     query_stats = (
#         analysis_df.with_columns(
#             (pl.col("Relevance") == "Yes").fill_null(False).cast(pl.Int64).alias("is_relevant")
#         )
#         .group_by("Query")
#         .agg(
#             [
#                 pl.count().alias("total_articles"),
#                 pl.col("is_relevant").sum().alias("relevant_articles"),
#                 (pl.col("is_relevant").mean() * 100).alias("relevance_rate_pct"),
#             ]
#         )
#         .sort(["relevance_rate_pct", "relevant_articles"], descending=True)
#     )
#
#     print(f"Top queries by relevance rate (min 5 articles) [{title}]:")
#     print(query_stats.filter(pl.col("total_articles") >= 5).head(20))
#
#     query_stats.write_csv(f"query_relevance_stats{suffix}.csv")
#
#     unique_relevant = (
#         analysis_df.filter(pl.col("Relevance") == "Yes")
#         .group_by("Query")
#         .agg(
#             [
#                 pl.col("article_key").n_unique().alias("unique_relevant_articles"),
#                 pl.count().alias("relevant_rows"),
#             ]
#         )
#         .sort(["unique_relevant_articles", "relevant_rows"], descending=True)
#     )
#
#     print(f"Top queries by unique relevant articles [{title}]:")
#     print(unique_relevant.head(20))
#
#     unique_relevant.write_csv(f"query_unique_relevant_stats{suffix}.csv")
#
#     # Long vs short query effectiveness (length-based).
#     query_len_stats = (
#         analysis_df.with_columns(
#             (pl.col("Relevance") == "Yes").fill_null(False).cast(pl.Int64).alias("is_relevant"),
#             pl.when(pl.col("query_len") >= 100)
#             .then(pl.lit("long>=100"))
#             .otherwise(pl.lit("short<100"))
#             .alias("query_len_group"),
#         )
#         .group_by("query_len_group")
#         .agg(
#             [
#                 pl.count().alias("rows"),
#                 pl.col("Query").n_unique().alias("unique_queries"),
#                 pl.col("is_relevant").sum().alias("relevant_rows"),
#                 (pl.col("is_relevant").mean() * 100).alias("relevance_rate_pct"),
#                 pl.col("article_key").n_unique().alias("unique_articles"),
#                 pl.when(pl.col("is_relevant") == 1)
#                 .then(pl.col("article_key"))
#                 .otherwise(None)
#                 .n_unique()
#                 .alias("unique_relevant_articles"),
#             ]
#         )
#         .sort("query_len_group")
#     )
#
#     print(f"Query length effectiveness [{title}]:")
#     print(query_len_stats)
#     query_len_stats.write_csv(f"query_length_effectiveness{suffix}.csv")
#
#     # Top longest queries by relevance rate.
#     top_long = (
#         query_stats.join(
#             analysis_df.select(["Query", "query_len"]).unique(),
#             on="Query",
#             how="left",
#         )
#         .filter(pl.col("query_len") >= 100)
#         .sort(["relevance_rate_pct", "relevant_articles"], descending=True)
#         .head(10)
#     )
#     print(f"Top long queries by relevance rate [{title}]:")
#     print(top_long)
#
#     # Plot: relevance rate by query (top 20 by total_articles)
#     qs_plot = query_stats.sort("total_articles", descending=True).head(20).to_pandas()
#     plt.figure(figsize=(10, 6))
#     plt.barh(qs_plot["Query"], qs_plot["relevance_rate_pct"])
#     plt.gca().invert_yaxis()
#     plt.xlabel("Relevance rate (%)")
#     plt.title(f"Top 20 Queries by Volume: Relevance Rate ({title})")
#     plt.tight_layout()
#     plt.savefig(PLOTS_DIR / f"relevance_rate_by_query{suffix}.png", dpi=150)
#     plt.close()
#
#     # Plot: unique relevant articles by query (top 20)
#     ur_plot = unique_relevant.head(20).to_pandas()
#     plt.figure(figsize=(10, 6))
#     plt.barh(ur_plot["Query"], ur_plot["unique_relevant_articles"])
#     plt.gca().invert_yaxis()
#     plt.xlabel("Unique relevant articles")
#     plt.title(f"Top 20 Queries by Unique Relevant Articles ({title})")
#     plt.tight_layout()
#     plt.savefig(PLOTS_DIR / f"unique_relevant_by_query{suffix}.png", dpi=150)
#     plt.close()
#
#     def run_ilp_for_df(df: pl.DataFrame, label: str, plot_suffix: str) -> dict[str, dict]:
#         relevant = df.filter(pl.col("Relevance") == "Yes")
#         if not relevant.height:
#             print(f"No relevant rows for {label}. Skipping ILP.")
#             return {}
#
#         # Greedy set cover over queries to cover the most relevant articles.
#         relevant_for_cover = relevant.filter(pl.col("Query").is_not_null())
#         query_articles = (
#             relevant_for_cover.group_by("Query")
#             .agg(
#                 [
#                     pl.col("article_key").unique().alias("articles"),
#                     pl.count().alias("relevant_rows"),
#                 ]
#             )
#             .to_dicts()
#         )
#         query_articles_raw = list(query_articles)
#
#         all_articles = set(
#             relevant_for_cover.select("article_key").unique().drop_nulls().to_series().to_list()
#         )
#         covered_articles = set()
#         selected_queries = []
#
#         query_articles_work = list(query_articles)
#         while covered_articles != all_articles:
#             best = None
#             best_gain = 0
#             for row in query_articles_work:
#                 articles = set(row["articles"] or [])
#                 gain = len(articles - covered_articles)
#                 if gain > best_gain:
#                     best_gain = gain
#                     best = row
#             if best is None or best_gain == 0:
#                 break
#             selected_queries.append(best)
#             covered_articles |= set(best["articles"] or [])
#             query_articles_work = [r for r in query_articles_work if r["Query"] != best["Query"]]
#
#         total_articles = len(all_articles)
#         covered_pct = (len(covered_articles) / total_articles * 100) if total_articles else 0.0
#         print(
#             f"Greedy query cover [{label}]: {len(selected_queries)} queries cover {len(covered_articles)}/{total_articles} relevant articles ({covered_pct:.2f}%)"
#         )
#
#         # ILP ablation: exact minimum queries to reach coverage targets (100/95/90/85/80%).
#         queries = [row["Query"] for row in query_articles_raw if row.get("Query") and row.get("articles")]
#         article_sets = [
#             set(row["articles"] or []) for row in query_articles_raw if row.get("Query") and row.get("articles")
#         ]
#
#         union_articles = set().union(*article_sets) if article_sets else set()
#         if union_articles != all_articles:
#             missing = len(all_articles) - len(union_articles)
#             if missing > 0:
#                 print(f"ILP note: dropping {missing} articles with no query coverage")
#             all_articles = union_articles
#
#         articles_list = list(all_articles)
#         article_index = {a: i for i, a in enumerate(articles_list)}
#
#         n_q = len(queries)
#         n_a = len(articles_list)
#         if n_q == 0 or n_a == 0:
#             return {}
#
#         rows = []
#         cols = []
#         data = []
#
#         for q_idx, articles in enumerate(article_sets):
#             for a in articles:
#                 a_idx = article_index.get(a)
#                 if a_idx is None:
#                     continue
#                 rows.append(a_idx)
#                 cols.append(q_idx)
#                 data.append(1.0)
#
#         # Add -1 for y_a in each article constraint row.
#         for a_idx in range(n_a):
#             rows.append(a_idx)
#             cols.append(n_q + a_idx)
#             data.append(-1.0)
#
#         A1 = csr_matrix((data, (rows, cols)), shape=(n_a, n_q + n_a))
#         c = np.concatenate([np.ones(n_q), np.zeros(n_a)])
#         integrality = np.concatenate([np.ones(n_q, dtype=int), np.zeros(n_a, dtype=int)])
#         bounds = (np.zeros(n_q + n_a), np.ones(n_q + n_a))
#
#         targets = [100, 95, 90, 85, 80]
#         print(f"ILP ablation (min queries to reach coverage targets) [{label}]:")
#         ilp_solutions = {}
#         ilp_costs = {}
#         for t in targets:
#             target_count = int(np.ceil((t / 100) * n_a))
#             A2 = csr_matrix(([1.0] * n_a, ([0] * n_a, [n_q + i for i in range(n_a)])), shape=(1, n_q + n_a))
#             constraints = [
#                 LinearConstraint(A1, lb=0, ub=np.inf),
#                 LinearConstraint(A2, lb=target_count, ub=np.inf),
#             ]
#             res = milp(c, integrality=integrality, bounds=bounds, constraints=constraints, options={"time_limit": 30})
#             if res.success:
#                 x = res.x[:n_q]
#                 selected_idx = [i for i, v in enumerate(x) if v >= 0.5]
#                 ilp_solutions[t] = selected_idx
#                 selected_count = len(selected_idx)
#                 print(f"{t}%: {selected_count}")
#             else:
#                 print(f"{t}%: not solved ({res.status}) {getattr(res, 'message', '')}")
#
#         # Cost analysis for ILP solutions (savings vs all-data total costs).
#         result_costs_subset = df.with_columns(
#             [
#                 pl.col("price").cast(pl.Float64, strict=False).fill_null(0.0).alias("valyu_cost"),
#                 pl.col("LLM_Price").cast(pl.Float64, strict=False).fill_null(0.0).alias("llm_cost"),
#             ]
#         ).with_columns(
#             pl.when(pl.col("llm_ts").is_not_null())
#             .then(pl.concat_str([pl.col("norm_url"), pl.col("llm_ts").cast(pl.Utf8)], separator="|"))
#             .otherwise(None)
#             .alias("llm_key")
#         )
#
#         total_cost_subset, valyu_cost_subset, llm_cost_subset = _costs_with_llm_cap(result_costs_subset)
#         print(f"Total cost (all data): {total_cost_all:.4f} = valyu {valyu_cost_all:.4f} + llm {llm_cost_all:.4f}")
#         print(f"Total cost ({label}): {total_cost_subset:.4f} = valyu {valyu_cost_subset:.4f} + llm {llm_cost_subset:.4f}")
#         if timespan_days is not None:
#             print(f"Timespan days: {timespan_days:.2f} (cost/day: {total_cost_all / timespan_days:.4f})")
#             print(f"Projected annual cost: {(total_cost_all / timespan_days) * 365:.2f}")
#
#         for t, idxs in ilp_solutions.items():
#             selected_query_set = {queries[i] for i in idxs}
#             subset_all = result_costs_all.filter(pl.col("Query").is_in(list(selected_query_set)))
#             subset_total, subset_valyu, subset_llm = _costs_with_llm_cap(subset_all)
#             savings = total_cost_all - subset_total
#             valyu_savings = valyu_cost_all - subset_valyu
#             llm_savings = llm_cost_all - subset_llm
#             ilp_costs[t] = {
#                 "total": subset_total,
#                 "valyu": subset_valyu,
#                 "llm": subset_llm,
#                 "savings": savings,
#                 "valyu_savings": valyu_savings,
#                 "llm_savings": llm_savings,
#             }
#             print(
#                 f"ILP {t}%: cost {subset_total:.4f} (valyu {subset_valyu:.4f}, llm {subset_llm:.4f}), "
#                 f"savings {savings:.4f} (valyu {valyu_savings:.4f}, llm {llm_savings:.4f})"
#             )
#             if timespan_days is not None:
#                 cost_per_day = subset_total / timespan_days
#                 savings_per_day = savings / timespan_days
#                 print(f"ILP {t}%: cost/day {cost_per_day:.4f}, savings/day {savings_per_day:.4f}")
#                 print(f"ILP {t}%: projected annual cost {cost_per_day * 365:.2f}, annual savings {savings_per_day * 365:.2f}")
#
#         # Plot: coverage vs min queries (ILP)
#         if ilp_solutions:
#             cov = sorted(ilp_solutions.keys())
#             min_q = [len(ilp_solutions[c]) for c in cov]
#             plt.figure(figsize=(6, 4))
#             plt.plot(cov, min_q, marker="o")
#             plt.xlabel("Coverage target (%)")
#             plt.ylabel("Minimum queries (ILP)")
#             plt.title(f"Minimum Queries vs Coverage ({label})")
#             plt.grid(True, alpha=0.3)
#             plt.tight_layout()
#             plt.savefig(PLOTS_DIR / f"min_queries_vs_coverage{plot_suffix}.png", dpi=150)
#             plt.close()
#
#         # Plot: cost vs coverage & savings vs coverage
#         if ilp_costs:
#             cov = sorted(ilp_costs.keys())
#             costs = [ilp_costs[c]["total"] for c in cov]
#             costs_valyu = [ilp_costs[c]["valyu"] for c in cov]
#             costs_llm = [ilp_costs[c]["llm"] for c in cov]
#             savings = [ilp_costs[c]["savings"] for c in cov]
#             savings_valyu = [ilp_costs[c]["valyu_savings"] for c in cov]
#             savings_llm = [ilp_costs[c]["llm_savings"] for c in cov]
#             plt.figure(figsize=(6, 4))
#             plt.plot(cov, costs, marker="o", label="Total")
#             plt.plot(cov, costs_valyu, marker="o", label="Valyu")
#             plt.plot(cov, costs_llm, marker="o", label="LLM")
#             plt.xlabel("Coverage target (%)")
#             plt.ylabel("Total cost")
#             plt.title(f"Cost vs Coverage (ILP) ({label})")
#             plt.legend()
#             plt.grid(True, alpha=0.3)
#             plt.tight_layout()
#             plt.savefig(PLOTS_DIR / f"cost_vs_coverage{plot_suffix}.png", dpi=150)
#             plt.close()
#
#             plt.figure(figsize=(6, 4))
#             plt.plot(cov, savings, marker="o", label="Total")
#             plt.plot(cov, savings_valyu, marker="o", label="Valyu")
#             plt.plot(cov, savings_llm, marker="o", label="LLM")
#             plt.xlabel("Coverage target (%)")
#             plt.ylabel("Savings vs full cost")
#             plt.title(f"Savings vs Coverage (ILP) ({label})")
#             plt.legend()
#             plt.grid(True, alpha=0.3)
#             plt.tight_layout()
#             plt.savefig(PLOTS_DIR / f"savings_vs_coverage{plot_suffix}.png", dpi=150)
#             plt.close()
#
#         return ilp_costs
#
#     report_costs_df = analysis_df.with_columns(
#         [
#             pl.col("price").cast(pl.Float64, strict=False).fill_null(0.0).alias("valyu_cost"),
#             pl.col("LLM_Price").cast(pl.Float64, strict=False).fill_null(0.0).alias("llm_cost"),
#         ]
#     ).with_columns(
#         pl.when(pl.col("llm_ts").is_not_null())
#         .then(pl.concat_str([pl.col("norm_url"), pl.col("llm_ts").cast(pl.Utf8)], separator="|"))
#         .otherwise(None)
#         .alias("llm_key")
#     )
#     total_cost_subset, valyu_cost_subset, llm_cost_subset = _costs_with_llm_cap(report_costs_df)
#
#     report_path = Path(f"analysis_report{suffix}.md")
#     with report_path.open("w", encoding="utf-8") as f:
#         f.write(f"# {title} Query Relevance and Coverage Report\n\n")
#         f.write("## I. Introduction\n")
#         f.write(
#             "This report analyzes news ingestion data to identify which queries yield the most relevant articles, "
#             "optimize query coverage, and quantify cost savings from reduced query sets.\n\n"
#         )
#         f.write("## II. Methodology\n")
#         f.write(
#             "- Joined Valyu and LLM data on normalized URL plus a 1-hour timestamp tolerance.\n"
#             "- Used `duplicate_key` (fallback to normalized URL) to define unique articles.\n"
#             f"- Filtered to {title} events only.\n"
#             "- Defined relevance as `Relevance == \"Yes\"`.\n"
#             "- Solved minimum-query coverage with an exact ILP for 100/95/90/85/80% targets.\n\n"
#         )
#         f.write("## III. Results\n")
#         f.write(f"- Total cost (all data): {total_cost_all:.4f} (Valyu {valyu_cost_all:.4f}, LLM {llm_cost_all:.4f}).\n")
#         f.write(f"- Total cost ({title}): {total_cost_subset:.4f} (Valyu {valyu_cost_subset:.4f}, LLM {llm_cost_subset:.4f}).\n")
#         if timespan_days is not None:
#             f.write(f"- Timespan: {timespan_days:.2f} days; cost/day {total_cost_all / timespan_days:.4f}.\n")
#             f.write(f"- Projected annual cost: {(total_cost_all / timespan_days) * 365:.2f}.\n")
#         all_ilp = run_ilp_for_df(analysis_df, f"{title} (All Queries)", f"{suffix}")
#         short_ilp = run_ilp_for_df(
#             analysis_df.filter(pl.col("query_len") < 100),
#             f"{title} (Short Queries)",
#             f"{suffix}_short",
#         )
#         long_ilp = run_ilp_for_df(
#             analysis_df.filter(pl.col("query_len") >= 100),
#             f"{title} (Long Queries)",
#             f"{suffix}_long",
#         )
#         for label, ilp in [
#             ("All Queries", all_ilp),
#             ("Short Queries", short_ilp),
#             ("Long Queries", long_ilp),
#         ]:
#             if not ilp:
#                 f.write(f"- {label}: no ILP results (no relevant rows or queries).\n")
#                 continue
#             for t in sorted(ilp.keys()):
#                 entry = ilp[t]
#                 f.write(
#                     f"- {label} ILP {t}%: cost {entry['total']:.4f} (Valyu {entry['valyu']:.4f}, LLM {entry['llm']:.4f}), "
#                     f"savings {entry['savings']:.4f} (Valyu {entry['valyu_savings']:.4f}, LLM {entry['llm_savings']:.4f}).\n"
#                 )
#         f.write("\n")
#         f.write("Figures:\n")
#         f.write(f"- {PLOTS_DIR / f'relevance_rate_by_query{suffix}.png'}\n")
#         f.write(f"- {PLOTS_DIR / f'unique_relevant_by_query{suffix}.png'}\n")
#         f.write(f"- {PLOTS_DIR / f'min_queries_vs_coverage{suffix}.png'}\n")
#         f.write(f"- {PLOTS_DIR / f'cost_vs_coverage{suffix}.png'}\n")
#         f.write(f"- {PLOTS_DIR / f'savings_vs_coverage{suffix}.png'}\n")
#         f.write(f"- {PLOTS_DIR / f'min_queries_vs_coverage{suffix}_short.png'}\n")
#         f.write(f"- {PLOTS_DIR / f'cost_vs_coverage{suffix}_short.png'}\n")
#         f.write(f"- {PLOTS_DIR / f'savings_vs_coverage{suffix}_short.png'}\n")
#         f.write(f"- {PLOTS_DIR / f'min_queries_vs_coverage{suffix}_long.png'}\n")
#         f.write(f"- {PLOTS_DIR / f'cost_vs_coverage{suffix}_long.png'}\n")
#         f.write(f"- {PLOTS_DIR / f'savings_vs_coverage{suffix}_long.png'}\n\n")
#         f.write("## IV. Discussion\n")
#         f.write(
#             "Targeted queries produce higher relevance rates than broad categories, and a relatively small "
#             "subset of queries can cover most relevant articles. Cost reductions scale meaningfully as coverage "
#             "targets decrease from 100% to 80%.\n\n"
#         )
#         f.write("## V. Recommendations\n")
#         f.write(
#             "1) Prioritize high-yield, focused queries and deprecate low-relevance broad queries.\n"
#             "2) Adopt coverage tiers (100/95/90/85/80%) based on acceptable recall vs cost trade-offs.\n"
#             "3) Recompute relevance and coverage quarterly to account for query drift.\n"
#             "4) Use `duplicate_key` as the primary article identity for consistent deduplication.\n"
#         )
#
#
# analyze_subset(result, "", "All Events")
# analyze_subset(result.filter(pl.col("AlertFlag") == "Red"), "_red", "Red Alerts")
# joined.write_csv("combined_valyu_llm_stats.csv")
# print(result)
