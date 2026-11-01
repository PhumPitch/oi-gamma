"""Export full-chain snapshots from the database to Parquet files on this PC.

One file per day: data/chains/YYYY-MM-DD.parquet (all tickers). Days that already
have a file are skipped, so it is safe to run many times. Use --force to rewrite.
Run weekly, before the 30-day prune removes old days.

Run from the project folder: python -m scripts.export_parquet
"""
import argparse
from pathlib import Path

import pandas as pd
import sqlalchemy as sa

from src import history

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "chains"


def export(out_dir: Path = OUT_DIR, force: bool = False) -> list[str]:
    """Write one Parquet file per missing day. Returns the days written."""
    s = history.SNAPSHOTS.c
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    with history.engine().connect() as con:
        days = con.execute(sa.select(s.date).distinct().order_by(s.date)).scalars().all()
        for day in days:
            path = out_dir / f"{day}.parquet"
            if path.exists() and not force:
                continue
            df = pd.read_sql(sa.select(history.SNAPSHOTS).where(s.date == day), con)
            df.to_parquet(path, index=False)  # needs pyarrow
            written.append(day)
            print(f"{day}  {len(df):>7} rows -> {path.name}")
    return written


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--force", action="store_true", help="rewrite days that already have a file")
    written = export(force=p.parse_args().force)
    print(f"Done: {len(written)} new file(s) in {OUT_DIR}")


if __name__ == "__main__":
    main()
