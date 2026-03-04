"""
download_datasets.py
--------------------
Downloads three energy-related datasets into the project folder:
  1. IEA Hydrogen Projects Database
  2. EIA Form 860M – Planned Electric Generators (most recent month available)
  3. EPA LMOP – Landfill Methane Outreach Program project data

Usage:
    python download_datasets.py
"""

import io
import os
import sys
import time
from pathlib import Path

import requests
import pandas as pd

# ── Output directory (same folder as this script) ─────────────────────────────
OUT_DIR = Path(__file__).parent
OUT_DIR.mkdir(parents=True, exist_ok=True)

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def fetch_binary(url: str, label: str, timeout: int = 60):
    """GET a URL and return raw bytes, or None on failure."""
    print(f"  → Trying: {url}")
    try:
        resp = SESSION.get(url, timeout=timeout, stream=True)
        resp.raise_for_status()
        data = b"".join(resp.iter_content(chunk_size=65536))
        if len(data) < 512:
            print(f"  ✗ Response too small ({len(data)} bytes) – likely an error page.")
            return None
        print(f"  ✓ Downloaded {len(data):,} bytes.")
        return data
    except requests.HTTPError as e:
        print(f"  ✗ HTTP {e.response.status_code}: {e}")
    except requests.ConnectionError as e:
        print(f"  ✗ Connection error: {e}")
    except requests.Timeout:
        print(f"  ✗ Request timed out after {timeout}s.")
    except Exception as e:
        print(f"  ✗ Unexpected error: {e}")
    return None


def save_excel_sheet_as_csv(raw: bytes, sheet: str, out_path: Path, label: str) -> bool:
    """Parse an Excel file from bytes and save one sheet as CSV."""
    try:
        xls = pd.ExcelFile(io.BytesIO(raw), engine="openpyxl")
        # Try exact sheet name first, then fuzzy match
        target_sheet = None
        for name in xls.sheet_names:
            if sheet.lower() in name.lower():
                target_sheet = name
                break
        if target_sheet is None:
            print(f"  ✗ Sheet '{sheet}' not found. Available: {xls.sheet_names}")
            return False
        df = xls.parse(target_sheet)
        df.to_csv(out_path, index=False)
        print(f"  ✓ Saved '{target_sheet}' sheet → {out_path.name}  ({len(df):,} rows)")
        return True
    except Exception as e:
        print(f"  ✗ Failed to parse Excel: {e}")
        return False


def save_bytes_as_csv_direct(raw: bytes, out_path: Path) -> bool:
    """Assume raw bytes are already CSV; just write to disk."""
    try:
        out_path.write_bytes(raw)
        df = pd.read_csv(out_path, nrows=0)  # validate
        print(f"  ✓ Saved CSV → {out_path.name}")
        return True
    except Exception as e:
        print(f"  ✗ Could not parse as CSV: {e}")
        out_path.unlink(missing_ok=True)
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# 1. IEA Hydrogen Projects Database  (two separate files from IEA)
#    – iea_hydrogen_production_projects.csv     (manually downloaded, now cleaned)
#    – iea_hydrogen_infrastructure_projects.csv (manually downloaded, needs re-export)
# ───────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("[1/3] IEA Hydrogen Projects Database")
print("=" * 60)

IEA_PROD_OUT    = OUT_DIR / "iea_hydrogen_production_projects.csv"
IEA_PIPE_OUT    = OUT_DIR / "iea_hydrogen_infrastructure_H2_pipeline_projects.csv"
IEA_BLEND_OUT   = OUT_DIR / "iea_hydrogen_infrastructure_H2_Blending_projects.csv"

def check_and_clean_iea_file(path: Path, header_row: int, key_col: str) -> bool:
    """Check if an IEA CSV exists and has the correct header; clean if needed."""
    if not path.exists():
        return False
    try:
        df = pd.read_csv(path, nrows=0)
        if key_col in df.columns:
            row_count = sum(1 for _ in open(path)) - 1
            print(f"  ✓ Already clean: {path.name}  ({row_count:,} rows)")
            return True
        # Raw IEA multi-row header – fix it
        df_full = pd.read_csv(path, header=header_row)
        df_full = df_full.loc[:, ~df_full.columns.str.startswith("Unnamed")]
        df_full = df_full.dropna(subset=[key_col], how="all")
        df_full.to_csv(path, index=False)
        print(f"  ✓ Cleaned: {path.name}  ({len(df_full):,} rows x {len(df_full.columns)} cols)")
        return True
    except Exception as e:
        print(f"  ✗ Could not process {path.name}: {e}")
        return False

iea_prod_ok  = check_and_clean_iea_file(IEA_PROD_OUT,  header_row=2, key_col="Project name")
iea_pipe_ok  = check_and_clean_iea_file(IEA_PIPE_OUT,  header_row=3, key_col="Project name")
iea_blend_ok = check_and_clean_iea_file(IEA_BLEND_OUT, header_row=3, key_col="Project name")
iea_ok = iea_prod_ok

if not iea_prod_ok:
    print(
        "\n  ⚠  Production file missing – IEA requires a free registered account.\n"
        "  Manual steps:\n"
        "    1. Go to https://www.iea.org/data-and-statistics/data-product/hydrogen-projects-database\n"
        "    2. Sign in (free) and download the 'Production Projects' tab.\n"
        "    3. Save as:  iea_hydrogen_production_projects.csv\n"
    )
if not iea_pipe_ok:
    print(
        "\n  ⚠  Pipeline file missing.\n"
        "  Download the 'H2 Pipeline' tab from the IEA database and save as:\n"
        "    iea_hydrogen_infrastructure_H2_pipeline_projects.csv\n"
    )
if not iea_blend_ok:
    print(
        "\n  ⚠  Blending file missing.\n"
        "  Download the 'H2 Blending' tab from the IEA database and save as:\n"
        "    iea_hydrogen_infrastructure_H2_Blending_projects.csv\n"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 2. EIA Form 860M – Planned Electric Generators
# ───────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("[2/3] EIA Form 860M – Planned Electric Generators")
print("=" * 60)

EIA_OUT = OUT_DIR / "eia_860m_planned.csv"

# Build a list of candidate URLs from most-recent to older months
# Pattern: https://www.eia.gov/electricity/data/eia860m/xls/{month}_generator{year}.xlsx
MONTHS = [
    "december", "november", "october", "september",
    "august", "july", "june", "may",
]
YEARS = [2025, 2024]

EIA_URLS = []
for year in YEARS:
    for month in MONTHS:
        EIA_URLS.append(
            f"https://www.eia.gov/electricity/data/eia860m/xls/{month}_generator{year}.xlsx"
        )
        EIA_URLS.append(
            f"https://www.eia.gov/electricity/data/eia860m/archive/xls/{month}_generator{year}.xlsx"
        )

eia_ok = False
for url in EIA_URLS:
    raw = fetch_binary(url, "EIA 860M")
    if raw:
        if save_excel_sheet_as_csv(raw, "Planned", EIA_OUT, "EIA 860M"):
            eia_ok = True
            break
    time.sleep(0.5)

if not eia_ok:
    print(
        "\n  ⚠  Could not retrieve EIA 860M automatically.\n"
        "  Manual steps:\n"
        "    1. Go to https://www.eia.gov/electricity/data/eia860m/\n"
        "    2. Download the most recent Excel file.\n"
        "    3. Open it, go to the 'Planned' sheet, and save as:  eia_860m_planned.csv\n"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 3. EPA LMOP – Landfill Methane Outreach Program
# ───────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("[3/3] EPA LMOP – Landfill Gas Energy Project Data")
print("=" * 60)

LMOP_OUT = OUT_DIR / "epa_lmop_projects.csv"

LMOP_URLS = [
    # Under-construction & planned projects (scraped from EPA LMOP page 2024-09)
    "https://www.epa.gov/system/files/documents/2024-09/underconsplannedlmopdata.xlsx",
    # Full detailed project database (fallback)
    "https://www.epa.gov/system/files/documents/2024-09/opprjslmopdata-detailed.xlsx",
]

LMOP_SHEET_CANDIDATES = ["LMOP Database", "Under", "Planned", "Project", "Candidate"]

lmop_ok = False
for url in LMOP_URLS:
    raw = fetch_binary(url, "EPA LMOP")
    if raw:
        # Try to find the under-construction/planned sheet
        try:
            xls = pd.ExcelFile(io.BytesIO(raw), engine="openpyxl")
            print(f"  Sheets available: {xls.sheet_names}")
            target = None
            for candidate in LMOP_SHEET_CANDIDATES:
                for name in xls.sheet_names:
                    if candidate.lower() in name.lower():
                        target = name
                        break
                if target:
                    break
            if target is None:
                # Fall back to the first sheet with actual data
                target = xls.sheet_names[0]
            df = xls.parse(target)
            df.to_csv(LMOP_OUT, index=False)
            print(f"  ✓ Saved sheet '{target}' → {LMOP_OUT.name}  ({len(df):,} rows)")
            lmop_ok = True
            break
        except Exception as e:
            print(f"  ✗ Failed to parse LMOP Excel: {e}")
    time.sleep(1)

if not lmop_ok:
    print(
        "\n  ⚠  Automatic download failed.\n"
        "  Manual steps:\n"
        "    1. Go to https://www.epa.gov/lmop/landfill-gas-energy-project-data\n"
        "    2. Download 'LMOP Database and Project Locator' (xlsx).\n"
        "    3. Open the 'Under-Construction or Planned' sheet and save as: epa_lmop_projects.csv\n"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Summary
# ───────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("Summary")
print("=" * 60)
results = {
    "iea_hydrogen_production_projects.csv":                    iea_prod_ok,
    "iea_hydrogen_infrastructure_H2_pipeline_projects.csv":    iea_pipe_ok,
    "iea_hydrogen_infrastructure_H2_Blending_projects.csv":    iea_blend_ok,
    "eia_860m_planned.csv":                                    eia_ok,
    "epa_lmop_projects.csv":                                   lmop_ok,
}
for fname, ok in results.items():
    status = "✓ Downloaded" if ok else "✗ Manual download needed"
    path = OUT_DIR / fname
    size = f"  ({path.stat().st_size:,} bytes)" if ok and path.exists() else ""
    print(f"  {status}: {fname}{size}")

if not all(results.values()):
    print(
        "\n  See the messages above for manual download instructions.\n"
        "  Once files are in place, re-run this script to confirm sizes.\n"
    )
else:
    print("\n  All datasets downloaded successfully!\n")
