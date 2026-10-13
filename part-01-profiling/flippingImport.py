"""Make the trade data one-way: every row becomes Exporter -> Importer.
 
For each row where flow_type is Import:
    - swap exporter_iso <-> importer_iso
    - swap exporter_name <-> importer_name
    - set flow_type to Export
Your original CSV is NOT changed. The result is saved as a new file.
 
Needs a .env file in the project folder containing:
    LOCAL_PATH_PROJECT='C:\\Users\\User\\Project KRR'
"""
import os
from pathlib import Path
 
import pandas as pd
from dotenv import load_dotenv
 
load_dotenv()
PROJECT = Path(os.getenv("LOCAL_PATH_PROJECT"))
IN_FILE = PROJECT / "dataset" / "edges_semiconductor_trade.csv"
OUT_FILE = PROJECT / "dataset" / "edges_semiconductor_trade_directed.csv"
 
# True  = after flipping, delete rows that are identical in EVERY column (trade value included)
# False = keep everything, just flip
DROP_DUPLICATES = True
 
YEAR, TIER, DESC = "year", "tier", "hs_description"
EXP_ISO, EXP_NAME = "exporter_iso", "exporter_name"
IMP_ISO, IMP_NAME = "importer_iso", "importer_name"
FLOW = "flow_type"
 
df = pd.read_csv(IN_FILE, encoding="utf-8-sig")
print(f"Rows loaded: {len(df)}")
 
# Which rows are Import (ignores spaces and upper/lower case)
is_import = df[FLOW].astype(str).str.strip().str.lower() == "import"
print(f"Import rows to flip: {is_import.sum()}")
 
# Remember which rows were originally Exports (used if DROP_DUPLICATES is True)
df["_flipped"] = is_import
 
# Swap the four columns on the Import rows
df.loc[is_import, [EXP_ISO, EXP_NAME, IMP_ISO, IMP_NAME]] = (
    df.loc[is_import, [IMP_ISO, IMP_NAME, EXP_ISO, EXP_NAME]].values
)
df.loc[is_import, FLOW] = "Export"
 
# Check: how many rows are now identical in every column (trade value included)?
key = [c for c in df.columns if c != "_flipped"]
n_dupes = df.duplicated(subset=key, keep=False).sum()
print(f"Rows identical to another row in every column: {n_dupes}")
 
# For information: same trade but a different trade value
same_trade = [YEAR, TIER, DESC, EXP_ISO, IMP_ISO]
n_diff = df.duplicated(subset=same_trade, keep=False).sum() - n_dupes
print(f"Rows with the same year/product/exporter/importer but a different value: {n_diff}")
 
if DROP_DUPLICATES:
    before = len(df)
    df = df.sort_values("_flipped", kind="stable")   # original Exports first
    df = df.drop_duplicates(subset=key, keep="first")
    print(f"Duplicates removed: {before - len(df)}")
 
df = df.drop(columns="_flipped")
df.to_csv(OUT_FILE, index=False, encoding="utf-8-sig")
print(f"Saved: {OUT_FILE}")
print(df[FLOW].value_counts().to_string())
 