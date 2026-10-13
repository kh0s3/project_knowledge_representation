"""Rule checks: load the data, then print each rule with its count.

Needs a .env file in the project folder containing:
    LOCAL_PATH_PROJECT='C:\\Users\\User\\Project KRR'
and the data file at: <project>/dataset/edges_semiconductor_trade.csv
"""
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

# ---- Path (comes from .env, nothing to change here) --------------------
load_dotenv()
PROJECT = Path(os.getenv("LOCAL_PATH_PROJECT"))
df = pd.read_csv(PROJECT / "dataset" / "edges_semiconductor_trade.csv",
                 encoding="utf-8-sig")

# ---- Column names (as in your file) ------------------------------------
YEAR = "year"
TIER = "tier"
DESCRIPTION = "hs_description"
EXPORTER_ISO = "exporter_iso"
EXPORTER = "exporter_name"
IMPORTER_ISO = "importer_iso"
IMPORTER = "importer_name"
FLOW = "flow_type"
VALUE = "trade_value_usd"


def show(n, question, result, meaning):
    print(f"\nCheck {n}: {question}\n  Result : {result}\n  Meaning: {meaning}")


# 1. Tier and description
allowed = {
    ("Tier_1_Equipment", "Semiconductor manufacturing machinery & photolithography (ASML/EUV)"),
    ("Tier_2_Wafers", "Chemical compounds doped for electronics; silicon wafers"),
    ("Tier_3A_Logic_Processors", "Processors and controllers, whether or not combined with memories (CPUs/GPUs)"),
    ("Tier_3B_Memory", "Electronic integrated circuits as memories (DRAM, NAND, HBM)"),
    ("Tier_3C_Other_ICs", "Other electronic integrated circuits (Analog, PMICs, Mixed-signal)"),
}
bad = sum((t, d) not in allowed for t, d in zip(df[TIER], df[DESCRIPTION]))
show(1, "Does every tier come with its correct description?",
     f"{bad} of {len(df)} rows break it",
     "0 means tier and description always agree, so one column is redundant.")

# 2. Importer must not equal exporter
# strip spaces and ignore upper/lower case so "ABC " and "abc" count as the same name
imp = df[IMPORTER].astype(str).str.strip().str.lower()
exp = df[EXPORTER].astype(str).str.strip().str.lower()
same = (imp == exp) & df[IMPORTER].notna() & df[EXPORTER].notna()
show(2, "Is the importer ever the same as the exporter?",
     f"{same.sum()} of {len(df)} rows break it",
     "0 means the rule holds. More than 0 means a country is trading with itself, "
     "which is either a data error or something worth checking.")

if same.any():
    print("\nRows where importer == exporter:")
    print(df[same].head(20).to_string())

# 3. Trade value must be positive
vals = pd.to_numeric(df[VALUE], errors="coerce")   # text or garbage becomes empty
not_positive = ~(vals > 0)                          # zero, negative, or empty
show(3, "Is trade_value_usd always greater than 0?",
     f"{not_positive.sum()} of {len(df)} rows break it "
     f"({(vals < 0).sum()} negative, {(vals == 0).sum()} zero, {vals.isna().sum()} empty)",
     "0 means every row has a real positive value.")

if not_positive.any():
    print("\nRows with a non-positive trade value:")
    print(df[not_positive].head(20).to_string())

# 4. (Diagnostic) Does every Import row have a matching Export row?
flow = df[FLOW].astype(str).str.strip().str.lower()
key_cols = [YEAR, TIER, DESCRIPTION, EXPORTER_ISO, IMPORTER_ISO]
export_keys = set(map(tuple, df.loc[flow == "export", key_cols].values))
imports = df[flow == "import"]
no_mirror = sum(tuple(k) not in export_keys for k in imports[key_cols].values)
show(4, "How many Import rows have NO matching Export row (same year, product, countries)?",
     f"{no_mirror} of {len(imports)} Import rows",
     "If 0, every Import row just repeats an Export row. If more than 0, "
     "deleting all Import rows would lose real trades.")



 
 
def clean_name(s):
    return s.astype(str).str.strip().str.lower()
 
 

 

# 5. Every country in the economy file must appear in the trade file
#    (as an importer or as an exporter)
# ---- CHANGE ME: the other file and its country column ------------------
ECON_FILE = PROJECT / "dataset" / "nodes_countries.csv"
ECON_COUNTRY = "country_name"
econ = pd.read_csv(ECON_FILE, encoding="utf-8-sig")
 
 
 
econ_countries = set(clean_name(econ[ECON_COUNTRY].dropna()))
as_importer = set(clean_name(df[IMPORTER].dropna()))
as_exporter = set(clean_name(df[EXPORTER].dropna()))
trade_countries = as_importer | as_exporter
 
missing = sorted(econ_countries - trade_countries)
in_both = econ_countries & trade_countries
show(5, "Does every country in the economy file appear in the trade file "
        "(as importer or exporter)?",
     f"{len(missing)} of {len(econ_countries)} economy countries are missing from the trade file",
     "0 means every economy country has trade rows. More than 0: look at the names below, "
     "some may just be spelled differently in the two files.")
 
print("\nEconomy countries NOT found in the trade file:")
print(missing)
print(f"\nCountries in both files: {len(in_both)}")
 
