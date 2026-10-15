"""
Load the three semiconductor trade CSVs into PostgreSQL for R2RML.

Run from the folder containing this script:
    python load_database.py

Requires a .env file next to this script:
    LOCAL_PATH_PROJECT=C:/path/to/your/project
    DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@127.0.0.1:5432/DBNAME

Expected CSV files under LOCAL_PATH_PROJECT/dataset:
    edges_semiconductor_trade.csv
    nodes_countries.csv
    supply_chain_tiers.csv

Tables created:
    trades
    countries
    tiers

All CSV values are stored as TEXT. This preserves codes, leading zeros,
and decimal strings without numeric conversion.

WARNING: Successful loading replaces the existing three tables.
"""

import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import Text, create_engine, text
from sqlalchemy.engine import URL


# Load the .env file located beside this script, regardless of the
# directory from which the script is executed.
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
load_dotenv(PROJECT_DIR / ".env")

PROJECT_ENV = os.getenv("LOCAL_PATH_PROJECT")
DATABASE_URL = os.getenv("DATABASE_URL")

if not PROJECT_ENV:
    sys.exit("LOCAL_PATH_PROJECT is missing from the .env file.")

if not DATABASE_URL:
    sys.exit("DATABASE_URL is missing from the .env file.")

DATA = Path(PROJECT_ENV).expanduser() / "dataset"

# PostgreSQL table name -> source CSV file
TABLES = {
    "trades": DATA / "edges_semiconductor_trade.csv",
    "countries": DATA / "nodes_countries.csv",
    "tiers": DATA / "supply_chain_tiers.csv",
}

# Columns required for the consistency checks below.
REQUIRED_COLUMNS = {
    "trades": {"tier", "exporter_iso", "importer_iso"},
    "countries": {"country_iso"},
    "tiers": {"tier_id"},
}


def frame(path):
    """Read a CSV as text and normalize column names."""
    df = pd.read_csv(
        path,
        dtype=str,
        keep_default_na=False,
    )

    # For example: "Exporter ISO" -> "exporter_iso"
    df.columns = [
        "_".join(c.strip().lower().split())
        for c in df.columns
    ]

    if df.columns.duplicated().any():
        duplicates = df.columns[df.columns.duplicated()].tolist()
        sys.exit(
            f"Duplicate columns after name normalization in {path.name}: "
            f"{duplicates}"
        )

    return df


def validate_frames(frames):
    """Check required columns and cross-table references before loading."""
    for table, df in frames.items():
        missing = REQUIRED_COLUMNS[table] - set(df.columns)

        if missing:
            sys.exit(
                f"Missing required columns in {table}: "
                f"{sorted(missing)}\n"
                f"Available columns: {list(df.columns)}"
            )

    trades = frames["trades"]
    tiers = frames["tiers"]
    countries = frames["countries"]

    def nonempty(values):
        return {value for value in values if value.strip()}

    missing_tiers = (
        nonempty(trades["tier"]) - nonempty(tiers["tier_id"])
    )

    trade_isos = (
        nonempty(trades["exporter_iso"])
        | nonempty(trades["importer_iso"])
    )
    country_isos = nonempty(countries["country_iso"])
    missing_countries = trade_isos - country_isos

    print("\nData consistency checks")
    print("-----------------------")
    print(
        "Tiers in trades but not in tiers:       "
        f"{sorted(missing_tiers) if missing_tiers else 'none'}"
    )
    print(
        "Countries in trades but not in countries: "
        f"{sorted(missing_countries) if missing_countries else 'none'}"
    )

    if missing_tiers or missing_countries:
        print(
            "\nWARNING: Some references have no matching row in the "
            "corresponding table. Review these before generating your graph."
        )


def main():
    # Check all files before connecting to PostgreSQL or replacing tables.
    for table, path in TABLES.items():
        if not path.is_file():
            sys.exit(f"CSV file not found for {table}: {path}")

    # Read and validate every CSV before modifying the database.
    frames = {}

    for table, path in TABLES.items():
        try:
            df = frame(path)
        except Exception as err:
            sys.exit(f"Could not read {path}:\n{err}")

        frames[table] = df
        print(f"Read {table:<10} {len(df):>8,} rows from {path.name}")

    validate_frames(frames)

    # Connect to PostgreSQL.
    try:
        engine = create_engine(DATABASE_URL)

        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    except Exception as err:
        sys.exit(
            "\nPostgreSQL connection failed. Check that Docker is running "
            "and DATABASE_URL in .env is correct.\n"
            f"Details: {err}"
        )

    # Replace all three tables within one transaction.
    # PostgreSQL can roll back these table replacements if an error occurs.
    try:
        with engine.begin() as connection:
            for table, df in frames.items():
                df.to_sql(
                    name=table,
                    con=connection,
                    if_exists="replace",
                    index=False,
                    dtype={column: Text() for column in df.columns},
                    chunksize=5000,
                )

    except Exception as err:
        engine.dispose()
        sys.exit(
            "\nDatabase loading failed. The transaction was rolled back "
            "where supported by PostgreSQL.\n"
            f"Details: {err}"
        )

    # Confirm that the tables were created and report their row counts.
    print("\nSuccessfully loaded into PostgreSQL")
    print("-----------------------------------")

    with engine.connect() as connection:
        for table in TABLES:
            count = connection.execute(
                text(f'SELECT COUNT(*) FROM "{table}"')
            ).scalar_one()

            print(f"{table:<10} {count:>8,} rows")

    # Hide the password when displaying the connection details.
    print(
        "\nDatabase:",
        engine.url.render_as_string(hide_password=True),
    )

    engine.dispose()


if __name__ == "__main__":
    main()
