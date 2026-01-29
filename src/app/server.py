from __future__ import annotations

from flask import Flask, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler

from config.settings import get_config
from services.pipeline import (
    cleanup_old_data,
    extract_news_info,
    fetch_news,
    generate_report,
    run_topic_modeling,
    save_news,
)
from services.storage import data_path, read_csv
from utils.rows import llm_rows_from_records, news_rows_from_records


def create_app() -> Flask:
    app = Flask(__name__)

    @app.route("/")
    def home():
        return jsonify({"status": "ok"})

    @app.route("/trigger/regular")
    def trigger_regular():
        hours = request.args.get("hours", default=1, type=int)
        rows = fetch_news(hours=hours, include_trending=False)
        save_news(rows)
        return jsonify({"status": "triggered", "hours": hours})

    @app.route("/trigger/trending")
    def trigger_trending():
        rows = fetch_news(hours=24, include_trending=True)
        save_news(rows)
        return jsonify({"status": "triggered", "trending": True})

    @app.route("/trigger/extract")
    def trigger_extract():
        rows = news_rows_from_records(read_csv(data_path("news_data.csv")))
        extract_news_info(rows)
        return jsonify({"status": "triggered", "task": "extract"})

    @app.route("/trigger/topic")
    def trigger_topic():
        rows = llm_rows_from_records(read_csv(data_path("news_data_with_llm_info.csv")))
        run_topic_modeling(rows)
        return jsonify({"status": "triggered", "task": "topic"})

    @app.route("/trigger/report")
    def trigger_report():
        rows = llm_rows_from_records(read_csv(data_path("df_with_response_and_topics.csv")))
        generate_report(rows)
        return jsonify({"status": "triggered", "task": "report"})

    @app.route("/trigger/full")
    def trigger_full():
        hours = request.args.get("hours", default=24, type=int)
        include_trending = request.args.get("trending", default=1, type=int) == 1
        manual_fetch_and_process(hours=hours, include_trending=include_trending)
        return jsonify({"status": "triggered", "task": "full", "hours": hours, "trending": include_trending})

    @app.route("/trigger/cleanup")
    def trigger_cleanup():
        cfg = get_config()
        removed = cleanup_old_data(cfg.cleanup_days_to_keep)
        return jsonify({"status": "triggered", "removed": removed})

    return app


def start_scheduler(app: Flask) -> BackgroundScheduler:
    cfg = get_config()
    scheduler = BackgroundScheduler()
    scheduler.add_job(lambda: fetch_and_process(app), "cron", hour=7)
    scheduler.add_job(lambda: cleanup_old_data(cfg.cleanup_days_to_keep), "cron", hour=6, minute=30)
    scheduler.start()
    return scheduler


def fetch_and_process(_app: Flask) -> None:
    manual_fetch_and_process(hours=24, include_trending=True)


def manual_fetch_and_process(hours: int = 24, include_trending: bool = True) -> None:
    rows = fetch_news(hours=hours, include_trending=include_trending)
    save_news(rows)
    rows = news_rows_from_records(read_csv(data_path("news_data.csv")))
    extract_news_info(rows)
    rows = llm_rows_from_records(read_csv(data_path("news_data_with_llm_info.csv")))
    run_topic_modeling(rows)
    rows = llm_rows_from_records(read_csv(data_path("df_with_response_and_topics.csv")))
    generate_report(rows)


def main() -> None:
    app = create_app()
    start_scheduler(app)
    app.run(host="0.0.0.0", port=5001)


if __name__ == "__main__":
    main()
