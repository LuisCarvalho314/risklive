from __future__ import annotations

import argparse

from services.pipeline import (
    cleanup_old_data,
    extract_news_info,
    fetch_news,
    generate_report,
    run_topic_modeling,
    run_topic_visualizations,
    save_news,
)
from services.storage import data_path, read_csv
from utils.rows import llm_rows_from_records, news_rows_from_records


def main() -> None:
    parser = argparse.ArgumentParser(prog="risklive")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch_cmd = sub.add_parser("fetch")
    fetch_cmd.add_argument("--hours", type=int, default=1)
    fetch_cmd.add_argument("--trending", action="store_true")

    sub.add_parser("extract")
    sub.add_parser("topic")
    sub.add_parser("visualize")
    sub.add_parser("report")
    full_cmd = sub.add_parser("full")
    full_cmd.add_argument("--hours", type=int, default=24)
    full_cmd.add_argument("--trending", type=int, default=1)

    cleanup_cmd = sub.add_parser("cleanup")
    cleanup_cmd.add_argument("--days", type=int, default=3)

    args = parser.parse_args()

    if args.command == "fetch":
        rows = fetch_news(hours=args.hours, include_trending=args.trending)
        save_news(rows)
    elif args.command == "extract":
        rows = news_rows_from_records(read_csv(data_path("news_data.csv")))
        extract_news_info(rows)
    elif args.command == "topic":
        rows = llm_rows_from_records(read_csv(data_path("news_data_with_llm_info.csv")))
        run_topic_modeling(rows)
    elif args.command == "visualize":
        run_topic_visualizations()
    elif args.command == "report":
        rows = llm_rows_from_records(read_csv(data_path("df_with_response_and_topics.csv")))
        generate_report(rows)
    elif args.command == "cleanup":
        cleanup_old_data(args.days)
    elif args.command == "full":
        from app.server import manual_fetch_and_process

        manual_fetch_and_process(hours=args.hours, include_trending=args.trending == 1)


if __name__ == "__main__":
    main()
