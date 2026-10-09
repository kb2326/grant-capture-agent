"""python -m rag build-cards | embed --model gemini|local [--max-usd X]"""

import argparse
import json

from app.config import get_settings
from db.session import make_engine, make_session_factory
from rag.card import build_cards
from rag.embed import COLUMNS, embed_cards, make_embedder


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m rag")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build-cards")
    emb = sub.add_parser("embed")
    emb.add_argument("--model", choices=sorted(COLUMNS), required=True)
    emb.add_argument("--max-usd", type=float, default=0.50)
    args = parser.parse_args(argv)
    settings = get_settings()
    with make_session_factory(make_engine(settings.database_url))() as session:
        if args.cmd == "build-cards":
            out = build_cards(session)
        else:
            price = settings.price_embedding_per_m if args.model == "gemini" else 0.0
            out = embed_cards(
                session,
                make_embedder(args.model, settings),
                column=COLUMNS[args.model],
                price_per_m=price,
                max_usd=args.max_usd,
            )
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
