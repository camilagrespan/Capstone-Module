import json
import os
import requests
from typing import Optional

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="H2 & Waste-to-Energy Projects Near Tribal Lands",
    page_icon="🛡️",
    layout="wide",
)

# ── Sidebar: Due Diligence (shown always; populates on click) ─────────────────
with st.sidebar:
    st.title("🛡️ Due Diligence")
    st.caption(
        "Click any project marker on the map to evaluate it against the "
        "Due Diligence checklist for Free, Prior, and Informed Consent (FPIC) "
        "and environmental justice standards."
    )
    st.markdown("---")

    # --- Project filters ---
    st.subheader("Project Filters")
    tech_options = [
        "Hydrogen",
        "Waste-to-Energy"
    ]
    tech_filter = st.multiselect(
        "Project type",
        options=tech_options,
        default=tech_options,
    )
    tribal_only = st.checkbox(
        "Show only projects within 50 miles of Tribal land",
        value=False,
    )
    st.markdown("---")

    selected = st.session_state.get("selected_project", None)
    if selected:
        near = selected.get("Near_Tribal_Land", False)
        if near:
            st.error(f"🚨 Within 50 miles of: **{selected.get('Nearest_Tribe', 'a Tribal boundary')}**")
        else:
            st.success("✓ Not within 50-mile Tribal buffer zone")
        st.subheader(selected.get("Project_Name", "Unknown Project"))
        st.markdown(f"**Developer:** {selected.get('Developer', 'N/A')}")
        st.markdown(f"**Technology:** {selected.get('Technology', 'N/A')}")
        st.markdown("---")
        st.markdown("#### ☑ Checklist")

        CHECKLIST = [
            ("FPIC_Obtained",
             "Was Free, Prior, and Informed Consent obtained from the affected Tribe(s)?"),
            ("Tribal_Consultation",
             "Has formal government-to-government consultation taken place?"),
            ("Treaty_Rights_Review",
             "Have treaty rights and ceded territory obligations been assessed?"),
            ("Tribal_EIA",
             "Has a Tribal Environmental Impact Assessment (TEIA) been conducted?"),
            ("Water_Rights",
             "Have potential impacts on Tribal water rights been evaluated?"),
            ("Cultural_Resources",
             "Have sacred sites and cultural resources been identified and protected?"),
            ("Economic_Benefit",
             "Does the project include revenue-sharing or direct economic benefit to the Tribe?"),
            ("Tribal_Labor",
             "Is there a Tribal hiring or workforce preference agreement?"),
            ("Monitoring_Rights",
             "Does the Tribe have independent monitoring and enforcement rights?"),
            ("Exit_Remediation_Plan",
             "Is there a decommissioning and land-remediation plan agreed to by the Tribe?"),
        ]

        responses = {}
        for key, question in CHECKLIST:
            responses[key] = st.checkbox(question, key=f"chk_{key}")

        answered_yes = sum(responses.values())
        total = len(CHECKLIST)
        score_pct = int(answered_yes / total * 100)

        st.markdown("---")
        st.markdown(f"**Compliance Score: {answered_yes}/{total} ({score_pct}%)**")
        color = "green" if score_pct >= 70 else ("orange" if score_pct >= 40 else "red")
        label = "✓ Adequate" if score_pct >= 70 else ("⚠ Partial" if score_pct >= 40 else "✗ Insufficient")
        st.markdown(
            f"<div style='background:{color};border-radius:6px;padding:6px;"
            f"text-align:center;color:white;font-weight:bold'>{label}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.info("← Click a project marker on the map to begin the Due Diligence evaluation.")

# ── Main page ─────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div style="background:rgba(255,180,80,0.15);color:#fff;text-align:center;
                padding:12px 16px;border-radius:6px;font-size:1.5rem;
                font-weight:700;margin-bottom:12px;
                border:1px solid rgba(255,160,50,0.3);">
        🧹 🚧 Pardon Our Dust — Website Under Construction 🚧 🧹
    </div>
    """,
    unsafe_allow_html=True,
)
st.title("🛡️ H2 & Waste-to-Energy Projects Near Tribal Lands")
st.markdown(
    "**Blue markers** = Hydrogen projects &nbsp;|&nbsp; "
    "**Orange markers** = Waste-to-Energy projects &nbsp;|&nbsp; "
    "**Blue shading** = Federally recognized Indian Reservation boundaries. "
    "Click a marker to open the Due Diligence checklist in the sidebar."
)

# ── Load all_projects.csv ───────────────────────────────────────────────────────
@st.cache_data
def load_threats(path: str) -> pd.DataFrame:
    return pd.read_csv(path)

try:
    df = load_threats("all_threats.csv")
except FileNotFoundError:
    st.error("all_threats.csv not found. Run build_all_threats.py first.")
    st.stop()


# ── Load Tribal Boundaries GeoJSON ────────────────────────────────────────────
@st.cache_data(show_spinner="Loading reservation boundary data…")
def load_tribal_geojson(path: str) -> Optional[dict]:
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        return json.load(f)

tribal_geojson = load_tribal_geojson("tribal_boundaries_simple.geojson")

# ── Helper: marker colour ──────────────────────────────────────────────────────
def marker_color(technology: str) -> str:
    if "hydrogen" in str(technology).lower():
        return "#1565C0"   # blue
    return "#E65100"       # orange (Waste-to-Energy)

# ── Build Folium map ───────────────────────────────────────────────────────────
# --- Apply sidebar filters ---
mask = pd.Series([False] * len(df), index=df.index)
if "Hydrogen" in tech_filter:
    mask |= df["Technology"].str.contains("Hydrogen",      case=False, na=False)
if "Waste-to-Energy" in tech_filter:
    mask |= df["Technology"].str.contains("Waste|Landfill", case=False, na=False)
if tribal_only:
    mask &= df["Near_Tribal_Land"] == True

df_filtered = df[mask].copy()
if not df_filtered.empty:
    df_map = df_filtered.dropna(subset=["Latitude", "Longitude"]).copy()
else:
    df_map = pd.DataFrame(columns=["Latitude", "Longitude"])

# Calculate map center after filtering
center_lat = df_map["Latitude"].mean() if len(df_map) else 39.5
center_lon = df_map["Longitude"].mean() if len(df_map) else -98.35

# ── Build Folium map ───────────────────────────────────────────────────────────
m = folium.Map(
    location=[center_lat, center_lon],
    zoom_start=4,
    tiles="CartoDB positron",
)

# Tribal boundary layer
if tribal_geojson:
    folium.GeoJson(
        tribal_geojson,
        name="Tribal Boundaries",
        style_function=lambda _: {
            "fillColor": "#4169E1",
            "color":     "#1a3a8f",
            "weight":    1.5,
            "fillOpacity": 0.25,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["NAME"],
            aliases=["Tribal Area:"],
            sticky=True,
        ),
    ).add_to(m)

# Project markers — added directly to map (FeatureGroups unsupported in this st_folium version)
for _, row in df_map.iterrows():
    color    = marker_color(row["Technology"])
    is_alert = bool(row.get("Near_Tribal_Land", False))
    tribe    = str(row.get("Nearest_Tribe", ""))
    tip      = f"{row['Project_Name']} | {row['Technology']}"
    popup_html = (
        f"<b>{row['Project_Name']}</b><br>"
        f"Developer: {row['Developer']}<br>"
        f"Technology: {row['Technology']}<br>"
        + (f"<span style='color:red'><b>🚨 Within 50 mi of: {tribe}</b></span>" if is_alert else "")
    )
    popup = folium.Popup(popup_html, max_width=300)

    # Draw a larger red ring behind alert markers so they stand out
    if is_alert:
        folium.CircleMarker(
            location=[row["Latitude"], row["Longitude"]],
            radius=7,
            color="#cc0000",
            weight=2,
            fill=False,
        ).add_to(m)

    folium.CircleMarker(
        location=[row["Latitude"], row["Longitude"]],
        radius=4,
        color=color,
        fill=True,
        fill_color=color,
        fill_opacity=0.9,
        weight=1.5,
        popup=popup,
        tooltip=tip,
    ).add_to(m)

# Legend
legend_html = """
<div style="position:fixed;bottom:30px;right:30px;z-index:9999;
     background:white;padding:10px 14px;border-radius:8px;
     border:1px solid #ccc;font-size:13px;line-height:1.9;color:#111">
  <b>Project Type</b><br>
  <span style="color:#1565C0;font-size:18px">●</span> Hydrogen<br>
  <span style="color:#E65100;font-size:18px">●</span> Waste-to-Energy<br>
  <span style="color:#cc0000;font-size:18px">◎</span> Within 50 mi of Tribal land
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

# ── Metrics row (above map) ──────────────────────────────────────────────────
alert_count = int(df["Near_Tribal_Land"].sum()) if "Near_Tribal_Land" in df.columns else 0
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Projects",    len(df))
c2.metric("Hydrogen",          len(df[df["Technology"].str.contains("Hydrogen",       case=False, na=False)]))
c3.metric("Waste-to-Energy",   len(df[df["Technology"].str.contains("Waste|Landfill", case=False, na=False)]))
c4.metric("🚨 Near Tribal Land", alert_count)

# ── Render map & capture click ─────────────────────────────────────────────────

# Force the folium iframe to render at full height (fixes "sliver" bug)
st.markdown(
    """
    <style>
    [data-testid="stCustomComponentV1"],
    [data-testid="stIFrame"],
    .stCustomComponentV1,
    iframe[title="streamlit_folium.st_folium"] {
        height: 620px !important;
        min-height: 620px !important;
        width: 100% !important;
    }
    [data-testid="stCustomComponentV1"] iframe,
    [data-testid="stIFrame"] iframe {
        height: 620px !important;
        min-height: 620px !important;
        width: 100% !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

map_data = st_folium(
    m,
    use_container_width=True,
    height=600,
    returned_objects=["last_object_clicked_tooltip"],
)

# Resolve clicked tooltip → matching project row → session state
if map_data and map_data.get("last_object_clicked_tooltip"):
    tip_val = str(map_data["last_object_clicked_tooltip"])
    if "|" in tip_val:
        clicked_name = tip_val.split("|")[0].strip()
        match = df[df["Project_Name"].str.strip() == clicked_name]
        if not match.empty:
            proj = match.iloc[0]
            new_sel = {
                "Project_Name":    proj["Project_Name"],
                "Developer":       str(proj["Developer"]),
                "Technology":      proj["Technology"],
                "Near_Tribal_Land": bool(proj.get("Near_Tribal_Land", False)),
                "Nearest_Tribe":   str(proj.get("Nearest_Tribe", "")),
            }
            if st.session_state.get("selected_project") != new_sel:
                st.session_state["selected_project"] = new_sel
                st.rerun()

# ── Alert summary expander ────────────────────────────────────────────────────
if alert_count and "Near_Tribal_Land" in df.columns:
    with st.expander(f"🚨 {alert_count} projects within 50 miles of a Tribal boundary", expanded=False):
        alert_df = df[df["Near_Tribal_Land"]].copy()
        st.dataframe(
            alert_df[["Project_Name", "Developer", "Technology", "Nearest_Tribe"]],
            width="stretch",
            hide_index=True,
        )

# ── Data table ────────────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("All Projects")
st.dataframe(df_filtered, width="stretch", hide_index=True)

# ── Drought Vulnerability Maps ─────────────────────────────────────────────────
st.markdown("---")
st.subheader("🌵 Drought Vulnerability Maps")
st.caption(
    "Current US drought conditions from the US Drought Monitor (USDM), "
    "updated weekly. Colors show drought severity: "
    "D0 Abnormally Dry → D4 Exceptional Drought."
)

# USDM official drought category colours and labels
_USDM_COLORS = {0: "#FFFF00", 1: "#FCD37F", 2: "#FFAA00", 3: "#E60000", 4: "#730000"}
_USDM_LABELS = {
    0: "D0 – Abnormally Dry",
    1: "D1 – Moderate Drought",
    2: "D2 – Severe Drought",
    3: "D3 – Extreme Drought",
    4: "D4 – Exceptional Drought",
}

@st.cache_data(show_spinner="Loading drought data…")
def load_usdm_geojson() -> Optional[dict]:
    if not os.path.exists("usdm_drought.geojson"):
        return None
    with open("usdm_drought.geojson", "r") as f:
        return json.load(f)

tab_usdm, tab_fema = st.tabs(["🌧️ US Drought Monitor", "📊 FEMA National Risk Index"])

with tab_usdm:
    usdm_geojson = load_usdm_geojson()
    if usdm_geojson is None:
        st.warning(
            "⚠️ `usdm_drought.geojson` not found. "
            "Run `python download_drought_data.py` to generate it."
        )
    else:
        # Read map date from first feature if available
        try:
            map_date = usdm_geojson["features"][0]["properties"].get("map_date", "latest")
        except (KeyError, IndexError):
            map_date = "latest"

        m_usdm = folium.Map(location=[39.5, -98.35], zoom_start=4, tiles="CartoDB positron")

        def _usdm_style(feature):
            dm = int(feature["properties"].get("dm_category", 0))
            return {
                "fillColor": _USDM_COLORS.get(dm, "#FFFFFF"),
                "color": "#555555",
                "weight": 0.5,
                "fillOpacity": 0.75,
            }

        folium.GeoJson(
            usdm_geojson,
            name="USDM Drought",
            style_function=_usdm_style,
            tooltip=folium.GeoJsonTooltip(
                fields=["dm_label"],
                aliases=["Drought Category:"],
                localize=True,
            ),
        ).add_to(m_usdm)

        # Add a manual legend as HTML
        legend_html = """
        <div style="position:fixed;bottom:30px;left:30px;z-index:9999;
                    background:white;padding:10px 14px;border-radius:8px;
                    border:1px solid #ccc;font-size:13px;line-height:1.8;">
          <b>Drought Category</b><br>
          <span style="background:#FFFF00;padding:2px 10px;margin-right:6px;">&nbsp;</span>D0 – Abnormally Dry<br>
          <span style="background:#FCD37F;padding:2px 10px;margin-right:6px;">&nbsp;</span>D1 – Moderate<br>
          <span style="background:#FFAA00;padding:2px 10px;margin-right:6px;">&nbsp;</span>D2 – Severe<br>
          <span style="background:#E60000;padding:2px 10px;margin-right:6px;">&nbsp;</span>D3 – Extreme<br>
          <span style="background:#730000;padding:2px 10px;margin-right:6px;">&nbsp;</span>D4 – Exceptional
        </div>
        """
        m_usdm.get_root().html.add_child(folium.Element(legend_html))

        st.caption(f"Data as of: **{map_date}** | Source: US Drought Monitor / University of Nebraska–Lincoln")
        st_folium(m_usdm, use_container_width=True, height=520, returned_objects=[])

with tab_fema:
    st.markdown("""
    ### FEMA National Risk Index — Drought Hazard

    The **FEMA National Risk Index (NRI)** scores every US county on drought hazard,
    combining expected annual loss, social vulnerability, and community resilience.

    The NRI drought hazard layer is not available via a public API; access it directly
    from FEMA's interactive map:

    🔗 **[Open FEMA NRI Interactive Map](https://hazards.fema.gov/nri/map)**

    On that map:
    - Select **Drought** from the hazard dropdown
    - Use the county detail panel to see Risk Score, Expected Annual Loss, and Social Vulnerability rating
    - Data is updated annually; current version is NRI November 2023
    """)
    st.info(
        "Tip: Cross-reference the USDM current drought conditions (left tab) "
        "with the FEMA NRI long-term drought risk scores to identify tribal communities "
        "facing both acute and chronic water stress.",
        icon="💡",
    )

