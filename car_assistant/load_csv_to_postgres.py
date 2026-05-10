#!/usr/bin/env python3
import argparse
import csv
import os
import shlex
import subprocess
import sys
from pathlib import Path


def quote_ident(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load a CSV file into PostgreSQL using COPY."
    )
    parser.add_argument(
        "--csv",
        default="autoscout_de_parsed.csv",
        help="Path to CSV file (default: autoscout_de_parsed.csv)",
    )
    parser.add_argument(
        "--table",
        default="autoscout_de_parsed",
        help="Destination table name (default: autoscout_de_parsed)",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", ""),
        help="PostgreSQL connection URL. Defaults to DATABASE_URL env var.",
    )
    parser.add_argument(
        "--truncate-first",
        action="store_true",
        help="Truncate the destination table before importing.",
    )
    return parser.parse_args()


def run_psql(database_url: str, sql: str, label: str) -> None:
    cmd = ["psql", database_url, "-v", "ON_ERROR_STOP=1", "-c", sql]
    print(f"[1/2] {label}")
    result = subprocess.run(cmd, text=True, capture_output=True)
    if result.returncode != 0:
        sys.stderr.write(result.stderr or "psql command failed.\n")
        raise RuntimeError(label)
    if result.stdout.strip():
        print(result.stdout.strip())


def main() -> int:
    args = parse_args()

    if not args.database_url:
        print(
            "Missing database URL. Provide --database-url or export DATABASE_URL.",
            file=sys.stderr,
        )
        return 1

    csv_path = Path(args.csv).resolve()
    if not csv_path.exists():
        print(f"CSV file not found: {csv_path}", file=sys.stderr)
        return 1

    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        try:
            headers = next(reader)
        except StopIteration:
            print("CSV file is empty.", file=sys.stderr)
            return 1

    table_ident = quote_ident(args.table)
    quoted_headers = [quote_ident(h) for h in headers]
    columns_sql = ", ".join(f"{h} TEXT" for h in quoted_headers)
    header_list = ", ".join(quoted_headers)

    create_sql = f"CREATE TABLE IF NOT EXISTS {table_ident} ({columns_sql});"
    copy_sql = (
        f"COPY {table_ident} ({header_list}) "
        f"FROM {quote_literal(str(csv_path))} WITH (FORMAT csv, HEADER true);"
    )

    try:
        run_psql(args.database_url, create_sql, "Creating table if needed")
        if args.truncate_first:
            run_psql(args.database_url, f"TRUNCATE TABLE {table_ident};", "Truncating table")
        print("[2/2] Importing CSV (this can take a while)")
        copy_cmd = [
            "psql",
            args.database_url,
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            copy_sql,
        ]
        print("Running:", " ".join(shlex.quote(c) for c in copy_cmd[:-2]), "-c <COPY SQL>")
        result = subprocess.run(copy_cmd, text=True, capture_output=True)
        if result.returncode != 0:
            sys.stderr.write(result.stderr or "COPY failed.\n")
            return 1
        if result.stdout.strip():
            print(result.stdout.strip())
    except FileNotFoundError:
        print(
            "psql is not installed or not in PATH. Install PostgreSQL client tools first.",
            file=sys.stderr,
        )
        return 1
    except RuntimeError:
        return 1

    print("CSV imported successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
