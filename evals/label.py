"""python -m evals.label  — open the labeling page at http://127.0.0.1:8765"""

import argparse
import threading
import webbrowser
from pathlib import Path

import uvicorn

from app.config import get_settings
from db.session import make_engine, make_session_factory
from evals.label_app import create_app


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--labeler", default="karthick")
    p.add_argument("--golden", default="evals/data/golden")
    p.add_argument("--manifest", default="evals/data/golden/m1_sample.json")
    args = p.parse_args()
    app = create_app(
        make_session_factory(make_engine(get_settings().database_url)),
        Path(args.golden),
        Path(args.manifest),
        args.labeler,
    )
    threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:8765")).start()
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")


if __name__ == "__main__":
    main()
