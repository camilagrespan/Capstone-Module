"""
label_projects.py
-----------------
Categorizes energy projects into:
  - Green Hydrogen
  - Blue Hydrogen
  - Grey Hydrogen
  - Waste-to-Energy
  - Other (fallback)

Rules
-----
Green Hydrogen : Technology contains 'Electrolysis'
                 AND (Energy_Source OR Technology) contains a renewable keyword
                 (Renewables, Wind, Solar, Hydro)

Blue Hydrogen  : Technology contains 'Natural Gas' or 'SMR'
                 AND Technology (or any available field) contains
                 'CCUS' or 'Carbon Capture'

Grey Hydrogen  : Technology contains 'SMR' or 'Natural Gas'
                 AND neither 'CCUS' nor 'Carbon Capture' is present

Waste-to-Energy: Technology contains 'Gasification', 'Thermal Conversion',
                 'Landfill Gas', or 'Waste'

Priority order: Green → Blue → Grey → Waste-to-Energy → Other
"""

import pandas as pd

# ── Keyword sets ──────────────────────────────────────────────────────────────
RENEWABLE_KEYWORDS  = {"renewables", "wind", "solar", "hydro"}
FOSSIL_KEYWORDS     = {"natural gas", "smr"}
CCUS_KEYWORDS       = {"ccus", "carbon capture"}
WTE_KEYWORDS        = {"gasification", "thermal conversion", "landfill gas", "waste"}


def _contains_any(text: str, keywords: set[str]) -> bool:
    """Return True if *text* contains any keyword (case-insensitive)."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


def label_project(row: pd.Series) -> str:
    """
    Classify a single DataFrame row as one of:
        'Green Hydrogen', 'Blue Hydrogen', 'Grey Hydrogen',
        'Waste-to-Energy', or 'Other'.

    Expected columns (all optional except 'Technology'):
        Technology    – primary classification field
        Energy_Source – if present, used to check renewable sources
    """
    tech   = str(row.get("Technology",    ""))
    source = str(row.get("Energy_Source", ""))  # may be empty / NaN

    # Combine tech + source into one searchable string
    combined = f"{tech} {source}"

    is_electrolysis = "electrolysis" in tech.lower()
    is_renewable    = _contains_any(combined, RENEWABLE_KEYWORDS)
    is_fossil       = _contains_any(tech,     FOSSIL_KEYWORDS)
    is_ccus         = _contains_any(combined, CCUS_KEYWORDS)
    is_wte          = _contains_any(tech,     WTE_KEYWORDS)

    # ── Priority rules ────────────────────────────────────────────────────────
    if is_electrolysis and is_renewable:
        return "Green Hydrogen"

    if is_fossil and is_ccus:
        return "Blue Hydrogen"

    if is_fossil and not is_ccus:
        return "Grey Hydrogen"

    if is_wte:
        return "Waste-to-Energy"

    return "Other"


def label_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply label_project() to every row and store the result in
    a new 'Project_Category' column.  Returns the modified DataFrame.
    """
    df = df.copy()
    df["Project_Category"] = df.apply(label_project, axis=1)
    return df


# ── Demo / standalone run ─────────────────────────────────────────────────────
if __name__ == "__main__":
    import os

    csv_path = "all_threats.csv"
    if not os.path.exists(csv_path):
        print(f"ERROR: {csv_path} not found. Run build_all_threats.py first.")
        raise SystemExit(1)

    df = pd.read_csv(csv_path)
    df = label_dataframe(df)

    print("\nCategory distribution:")
    print(df["Project_Category"].value_counts().to_string())

    print("\nSample rows:")
    cols = ["Project_Name", "Technology", "Project_Category"]
    if "Energy_Source" in df.columns:
        cols.insert(2, "Energy_Source")
    print(df[cols].head(20).to_string(index=False))

    out_path = "all_threats_labeled.csv"
    df.to_csv(out_path, index=False)
    print(f"\nLabeled data saved to {out_path}")
