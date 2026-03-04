import argparse
import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from services.worker import run_once


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a single worker cycle.")
    parser.add_argument("--mode", default="manual", choices=["manual", "hourly", "daily"])
    parser.add_argument("--hours", type=int, default=1)
    parser.add_argument("--sample", action="store_true", help="Use a sample article.")
    args = parser.parse_args()

    result = run_once(mode=args.mode, hours=args.hours, sample=args.sample)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
