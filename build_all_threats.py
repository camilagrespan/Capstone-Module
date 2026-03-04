"""
build_all_threats.py
--------------------
Loads five energy project CSV files, standardises them to:
    Project_Name | Developer | Technology | Latitude | Longitude
Filters to Hydrogen and Waste-to-Energy projects in the United States,
and saves the combined result as all_threats.csv.
"""

import pandas as pd

OUT_FILE = "all_threats.csv"

# ── Helpers ────────────────────────────────────────────────────────────────────
STANDARD_COLS = ["Project_Name", "Developer", "Technology", "Latitude", "Longitude"]

# ISO-3 country codes used by IEA for United States
US_ISO3 = {"USA", "US"}

def keep_us_iso3(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Filter to rows where the given column is a US ISO-3 code."""
    return df[df[col].str.upper().isin(US_ISO3)].copy()


# ══════════════════════════════════════════════════════════════════════════════
# 1. EIA Form 860M – Planned Generators  (header on row 2)
# ══════════════════════════════════════════════════════════════════════════════
print("[1/5] EIA Form 860M – Planned Generators")

eia_raw = pd.read_csv("eia_860m_planned.csv", header=2, dtype=str)

# Technology values relevant to Hydrogen / Waste-to-Energy
HYDROGEN_TECH_EIA = {"Fuel Cell"}          # Energy Source Code H2 also caught below
WTE_TECH_EIA      = {"Landfill Gas", "Municipal Solid Waste", "Other Waste Biomass"}
RELEVANT_EIA      = HYDROGEN_TECH_EIA | WTE_TECH_EIA

eia_filtered = eia_raw[
    eia_raw["Technology"].isin(RELEVANT_EIA)
    | eia_raw["Energy Source Code"].isin({"LFG", "OBG", "MSW", "H2"})
].copy()

def eia_tech_label(row):
    t = str(row.get("Technology", "")).strip()
    e = str(row.get("Energy Source Code", "")).strip()
    if t in HYDROGEN_TECH_EIA or e == "H2":
        return "Hydrogen – Fuel Cell"
    if t == "Landfill Gas" or e == "LFG":
        return "Waste-to-Energy – Landfill Gas"
    if t == "Municipal Solid Waste" or e == "MSW":
        return "Waste-to-Energy – Municipal Solid Waste"
    return f"Waste-to-Energy – {t or e}"

eia_filtered["_tech_label"] = eia_filtered.apply(eia_tech_label, axis=1)

eia_std = pd.DataFrame({
    "Project_Name": eia_filtered["Plant Name"],
    "Developer":    eia_filtered["Entity Name"],
    "Technology":   eia_filtered["_tech_label"],
    "Latitude":     pd.to_numeric(eia_filtered["Latitude"],  errors="coerce"),
    "Longitude":    pd.to_numeric(eia_filtered["Longitude"], errors="coerce"),
    "_source":      "EIA 860M",
})

print(f"  → {len(eia_std)} rows kept")


# ══════════════════════════════════════════════════════════════════════════════
# 2. EPA LMOP – Landfill Gas / Waste-to-Energy  (already US-only, no lat/lon)
# ══════════════════════════════════════════════════════════════════════════════
print("[2/5] EPA LMOP – Landfill Gas Projects")

lmop_raw = pd.read_csv("epa_lmop_projects.csv", dtype=str)

# Keep only planned / under-construction projects
planned_statuses = {"Planned", "Under Construction", "Under construction"}
lmop_filtered = lmop_raw[
    lmop_raw["Current Project Status"].isin(planned_statuses)
].copy()

def lmop_tech_label(row):
    ptype = str(row.get("LFG Energy Project Type", "")).strip()
    cat   = str(row.get("Project Type Category",   "")).strip()
    if ptype and ptype not in {"nan"}:
        return f"Waste-to-Energy – {ptype}"
    if cat and cat not in {"nan"}:
        return f"Waste-to-Energy – {cat}"
    return "Waste-to-Energy – Landfill Gas"

lmop_filtered["_tech_label"] = lmop_filtered.apply(lmop_tech_label, axis=1)

lmop_std = pd.DataFrame({
    "Project_Name": lmop_filtered["Project Name"].fillna(lmop_filtered["Landfill Name"]),
    "Developer":    lmop_filtered["Project Developer(s)"],
    "Technology":   lmop_filtered["_tech_label"],
    "Latitude":     float("nan"),   # LMOP dataset does not include coordinates
    "Longitude":    float("nan"),
    "_source":      "EPA LMOP",
})

print(f"  → {len(lmop_std)} rows kept")


# ══════════════════════════════════════════════════════════════════════════════
# 3. IEA Hydrogen Production Projects  (has Lat/Lon; filter Country == USA)
# ══════════════════════════════════════════════════════════════════════════════
print("[3/5] IEA Hydrogen Production Projects")

iea_prod = pd.read_csv("iea_hydrogen_production_projects.csv", dtype=str)

iea_prod_us = keep_us_iso3(iea_prod, "Country")

iea_prod_std = pd.DataFrame({
    "Project_Name": iea_prod_us["Project name"],
    "Developer":    iea_prod_us.get("References", pd.Series(dtype=str)),
    "Technology":   "Hydrogen – " + iea_prod_us["Technology"].fillna("Production"),
    "Latitude":     pd.to_numeric(iea_prod_us["Latitude"],  errors="coerce"),
    "Longitude":    pd.to_numeric(iea_prod_us["Longitude"], errors="coerce"),
    "_source":      "IEA Production",
})

print(f"  → {len(iea_prod_std)} rows kept  (of {len(iea_prod)} total)")


# ══════════════════════════════════════════════════════════════════════════════
# 4. IEA Hydrogen Pipeline Projects  (no lat/lon; filter Country1 == USA)
# ══════════════════════════════════════════════════════════════════════════════
print("[4/5] IEA Hydrogen Pipeline Projects")

iea_pipe = pd.read_csv("iea_hydrogen_infrastructure_H2_pipeline_projects.csv", dtype=str)

# A pipeline may cross borders; include it if any country column is USA
country_cols = [c for c in iea_pipe.columns if c.startswith("Country")]
us_mask = iea_pipe[country_cols].apply(
    lambda col: col.str.upper().isin(US_ISO3), axis=0
).any(axis=1)
iea_pipe_us = iea_pipe[us_mask].copy()

iea_pipe_std = pd.DataFrame({
    "Project_Name": iea_pipe_us["Project name"],
    "Developer":    iea_pipe_us["Partners"],
    "Technology":   "Hydrogen – Pipeline (" + iea_pipe_us["Pipeline_type"].fillna("Unknown") + ")",
    "Latitude":     float("nan"),
    "Longitude":    float("nan"),
    "_source":      "IEA Pipeline",
})

print(f"  → {len(iea_pipe_std)} rows kept  (of {len(iea_pipe)} total)")


# ══════════════════════════════════════════════════════════════════════════════
# 5. IEA Hydrogen Blending Projects  (no lat/lon; filter Country == USA)
# ══════════════════════════════════════════════════════════════════════════════
print("[5/5] IEA Hydrogen Blending Projects")

iea_blend = pd.read_csv("iea_hydrogen_infrastructure_H2_Blending_projects.csv", dtype=str)

iea_blend_us = keep_us_iso3(iea_blend, "Country")

iea_blend_std = pd.DataFrame({
    "Project_Name": iea_blend_us["Project name"],
    "Developer":    iea_blend_us["Partners"],
    "Technology":   "Hydrogen – Blending (" + iea_blend_us["H2_blend"].fillna("?") + ")",
    "Latitude":     float("nan"),
    "Longitude":    float("nan"),
    "_source":      "IEA Blending",
})

print(f"  → {len(iea_blend_std)} rows kept  (of {len(iea_blend)} total)")


# ══════════════════════════════════════════════════════════════════════════════
# Combine, clean, and save
# ══════════════════════════════════════════════════════════════════════════════
print("\nCombining and saving…")

combined = pd.concat(
    [eia_std, lmop_std, iea_prod_std, iea_pipe_std, iea_blend_std],
    ignore_index=True,
)

# Drop rows where Project_Name is blank
combined = combined[combined["Project_Name"].notna() & (combined["Project_Name"].str.strip() != "")]

# Strip whitespace from string columns
for col in ["Project_Name", "Developer", "Technology"]:
    combined[col] = combined[col].astype(str).str.strip().replace("nan", "")

# Final column order (drop internal _source helper after reporting)
source_counts = combined["_source"].value_counts().to_dict()
combined = combined[STANDARD_COLS + ["_source"]]

# Save
combined.drop(columns="_source").to_csv(OUT_FILE, index=False)

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n✓ Saved {len(combined):,} projects → {OUT_FILE}")
print("\nRows by source:")
for src, n in source_counts.items():
    print(f"  {src:<30} {n:>4} rows")
print("\nRows by technology category:")
combined["_category"] = combined["Technology"].str.split(" – ").str[0]
for cat, n in combined["_category"].value_counts().items():
    print(f"  {cat:<30} {n:>4}")
print("\nColumn preview:")
print(combined[STANDARD_COLS].head(5).to_string(index=False))
