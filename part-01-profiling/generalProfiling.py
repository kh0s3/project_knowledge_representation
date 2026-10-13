# %%
import os
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from dotenv import load_dotenv
from ydata_profiling import ProfileReport

try:
    from IPython.display import display
except ImportError:
    pass

# ============================================================
# 1. CONFIGURATION
# ============================================================

load_dotenv()  # reads LOCAL_PATH_PROJECT from the .env file
PROJECT = Path(os.getenv("LOCAL_PATH_PROJECT"))

# Where the reports and charts are saved (created if missing)
OUT_DIR = PROJECT /"part-01-profiling"/"output"
OUT_DIR.mkdir(exist_ok=True)

DATASETS = {
    "semiconductor_trade": PROJECT / "dataset" / "edges_semiconductor_trade.csv",
}

# CSV encoding. Change only if your CSV requires another encoding.
CSV_ENCODING = "utf-8-sig"
# Use True to display charts when running in a notebook.
SHOW_CHARTS = True


# ============================================================
# 2. DETECT WHETHER WE ARE RUNNING IN A NOTEBOOK
# ============================================================

try:
    IN_NOTEBOOK = get_ipython() is not None
except NameError:
    IN_NOTEBOOK = False


# ============================================================
# 3. SUMMARIZE DATA QUALITY
# ============================================================

def quality_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Return one row per column with its type, unique values,
    missing values, and missing-value percentage.
    """

    return pd.DataFrame({
        "dtype": df.dtypes.astype(str),
        "n_unique": df.nunique(dropna=True),
        "n_missing": df.isna().sum(),
        "pct_missing": (df.isna().mean() * 100).round(2),
    }).sort_values("pct_missing", ascending=False)


# ============================================================
# 4. PLOT MISSING VALUES
# ============================================================

def plot_missingness(
    summary: pd.DataFrame,
    dataset_name: str,
    output_dir: Path,
    top_n: int = 15,
) -> None:
    """Plot the columns with the highest percentage of missing data.
    Save the chart and display it when running interactively.
    """

    worst = summary[summary["pct_missing"] > 0].head(top_n)

    if worst.empty:
        print(f"{dataset_name}: no missing values found.")
        return

    fig, ax = plt.subplots(
        figsize=(9, max(3, 0.4 * len(worst)))
    )

    ax.barh(
        worst.index[::-1],
        worst["pct_missing"].iloc[::-1],
    )

    ax.set_xlabel("Missing values (%)")
    ax.set_title(f"{dataset_name} — Missing Values")
    ax.set_xlim(0, 100)

    fig.tight_layout()

    safe_name = "".join(
        c if c.isalnum() or c in "-_" else "_"
        for c in dataset_name
    )

    chart_path = output_dir / f"{safe_name}_missingness.png"
    fig.savefig(chart_path, dpi=150, bbox_inches="tight")

    if IN_NOTEBOOK and SHOW_CHARTS:
        plt.show()

    plt.close(fig)

    print(f"Saved missingness chart: {chart_path.name}")


# ============================================================
# 5. LOAD AND PROFILE EACH DATASET
# ============================================================

def profile_dataset(
    dataset_name: str,
    csv_path: Path,
) -> None:
    """Load a CSV, print its summary, and generate its HTML report."""

    csv_path = Path(csv_path)

    print("\n" + "=" * 65)
    print(f"Dataset: {dataset_name}")
    print(f"File: {csv_path}")
    print("=" * 65)

    if not csv_path.exists():
        print(f"ERROR: File not found: {csv_path}")
        print("Check the path in DATASETS at the top of this file.")
        return

    try:
        df = pd.read_csv(csv_path, encoding=CSV_ENCODING)
    except (UnicodeDecodeError, pd.errors.ParserError, OSError) as exc:
        print(f"ERROR: Could not read {csv_path.name}: {exc}")
        return

    print(f"Rows: {df.shape[0]:,}")
    print(f"Columns: {df.shape[1]:,}")

    if df.empty:
        print("WARNING: This dataset is empty.")
        return

    print("\nColumn quality summary:")
    summary = quality_summary(df)
    print(summary.to_string())

    # Save the summary as a CSV for later inspection.
    safe_name = "".join(
        c if c.isalnum() or c in "-_" else "_"
        for c in dataset_name
    )

    summary_path = OUT_DIR / f"{safe_name}_quality_summary.csv"
    summary.to_csv(summary_path, index_label="column")

    print(f"\nSaved quality summary: {summary_path.name}")

    # Create a missing-values chart.
    plot_missingness(summary, dataset_name, OUT_DIR)

    # Generate the full HTML profile.
    report_path = OUT_DIR / f"{safe_name}_profile.html"

    report = ProfileReport(
        df,
        title=f"{dataset_name} — Data Profile",
        minimal=True,
    )

    report.to_file(report_path)

    print(f"Saved HTML profile: {report_path.name}")

    # Show the report inside Jupyter or VS Code notebooks.
    if IN_NOTEBOOK:
        display(report.to_notebook_iframe())


# ============================================================
# 6. MAIN
# ============================================================

def main() -> None:
    if not DATASETS:
        print("No datasets configured. Add CSV files to DATASETS.")
        return

    for dataset_name, csv_path in DATASETS.items():
        profile_dataset(dataset_name, csv_path)

    print("\nProfiling finished.")


if __name__ == "__main__":
    main()
