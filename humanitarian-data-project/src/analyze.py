"""
analyze.py — Clean, merge and quantify the humanitarian factors, then
produce the figures used in the report.

Inputs (created by src/fetch_data.py):
    data/worldbank_indicators.csv   health / economy / food security / population
    data/emdat_events.csv           natural-hazard exposure (EM-DAT via UN HDX)
    data/displaced.csv              forced displacement (UNHCR Global Trends)

Outputs:
    data/country_year_panel.csv     one tidy row per country x year
    figures/fig1_trends.png         time series of global disaster impact
    figures/fig2_map_hazard.png     choropleth map: hazard exposure 2015-2024
    figures/fig3_scatter_gdp_mortality.png   wealth vs child survival
    figures/fig4_top_countries.png  bar chart: most-affected countries

Every step prints a short explanation so a beginner can follow the logic.
Usage:  python src/analyze.py
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")                      # no display needed on servers
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA, FIGS = ROOT / "data", ROOT / "figures"
FIGS.mkdir(exist_ok=True)

RECENT = (2015, 2024)          # window we call "the recent decade"


# ----------------------------------------------------------------------
# Step 1 — load & tidy
# ----------------------------------------------------------------------
def load():
    wb = pd.read_csv(DATA / "worldbank_indicators.csv")
    em = pd.read_csv(DATA / "emdat_events.csv")
    dp = pd.read_csv(DATA / "displaced.csv")

    em.columns = [c.strip() for c in em.columns]
    em = em.rename(columns={"ISO": "iso3", "Year": "year"})
    # EM-DAT damage column name contains commas -> normalise it
    dmg = [c for c in em.columns if "Damage" in c][0]
    em = em.rename(columns={dmg: "damage_usd"})

    print(f"Loaded: World Bank {wb.shape}, EM-DAT {em.shape}, displaced {dp.shape}")
    return wb, em, dp


# ----------------------------------------------------------------------
# Step 2 — quantify each factor at country level
# ----------------------------------------------------------------------
def build_panel(wb, em, dp):
    # --- Factor A: natural-hazard exposure -----------------------------
    # events per year AND people affected per 100,000 population,
    # averaged over the recent decade. Per-capita rates let us compare
    # small and large countries fairly.
    haz = (em[(em["year"] >= RECENT[0]) & (em["year"] <= RECENT[1])]
           .groupby(["iso3", "year"], as_index=False)
           .agg(events=("Total Events", "sum"),
                affected=("Total Affected", "sum"),
                deaths=("Total Deaths", "sum")))
    pop = wb[["iso3", "year", "population"]].dropna()
    haz = haz.merge(pop, on=["iso3", "year"], how="left")
    haz["affected_per_100k"] = 1e5 * haz["affected"] / haz["population"]
    haz_avg = (haz.groupby("iso3")
               .agg(hazard_events_per_year=("events", "mean"),
                    hazard_affected_per_100k=("affected_per_100k", "mean"))
               .reset_index())

    # --- Factor B: economic capacity -----------------------------------
    econ = (wb[wb["year"].between(*RECENT)]
            .groupby("iso3", as_index=False)
            .agg(gdp_per_capita=("gdp_per_capita", "mean")))

    # --- Factor C: health / vulnerability ------------------------------
    health = (wb[wb["year"].between(*RECENT)]
              .groupby("iso3", as_index=False)
              .agg(under5_mortality=("under5_mortality", "mean"),
                   undernourishment=("undernourishment", "mean")))

    # --- Factor D: forced displacement ---------------------------------
    disp = dp[dp["year"].between(*RECENT)].copy()
    disp = disp.groupby("iso3", as_index=False)["refugees_per_1000_pop"].mean() \
        .rename(columns={"refugees_per_1000_pop": "refugees_per_1000"})

    # --- merge everything onto the country list ------------------------
    names = wb[["iso3", "country"]].drop_duplicates("iso3")
    panel = (names.merge(haz_avg, on="iso3", how="left")
                  .merge(econ, on="iso3", how="left")
                  .merge(health, on="iso3", how="left")
                  .merge(disp, on="iso3", how="left"))
    panel = panel[panel["gdp_per_capita"].notna()]      # drop aggregates/no-data

    # Long-format panel with yearly values (for trend charts)
    yearly = (wb.merge(haz[["iso3", "year", "events", "affected"]],
                       on=["iso3", "year"], how="left")
                .merge(dp.rename(columns={"iso3": "iso3"}),
                       on=["iso3", "year"], how="left"))
    yearly.to_csv(DATA / "country_year_panel.csv", index=False)
    panel.to_csv(DATA / "country_snapshot.csv", index=False)
    print(f"Panel built: {len(panel)} countries x {panel.shape[1]} columns")
    return panel, yearly


# ----------------------------------------------------------------------
# Step 3 — visualisations
# ----------------------------------------------------------------------
def fig1_trends(em):
    """Global yearly disaster impact -> shows the 'pressure over time'."""
    yr = (em.groupby("year", as_index=False)
            .agg(events=("Total Events", "sum"),
                 affected=("Total Affected", "sum")))
    yr = yr[(yr["year"] >= 2000) & (yr["year"] <= 2024)]
    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.bar(yr["year"], yr["events"], color="#c6dbef", label="Disaster events")
    ax1.set_ylabel("Recorded disaster events per year")
    ax2 = ax1.twinx()
    ax2.plot(yr["year"], yr["affected"] / 1e6, color="#d6604d", lw=2,
             marker="o", ms=3, label="People affected")
    ax2.set_ylabel("People affected (millions)")
    ax1.set_title("Figure 1 — Are disasters getting worse? Events vs. people affected, 2000–2024\n"
                  "(Source: EM-DAT Country Profiles via UN HDX)", fontsize=11)
    fig.tight_layout()
    fig.savefig(FIGS / "fig1_trends.png", dpi=150)
    plt.close(fig)


def fig2_map(panel):
    """Choropleth-style map using geopandas if available; otherwise a
    ranked horizontal bar 'map substitute' so students without geo tooling
    can still see the geography of exposure."""
    try:
        import geopandas as gpd
        import urllib.request
        shp = ROOT / "data" / "ne_50m_admin_0_countries.zip"
        if not shp.exists():
            urllib.request.urlretrieve(
                "https://naciscdn.org/naturalearth/50m/cultural/ne_50m_admin_0_countries.zip",
                shp)
        world = gpd.read_file(shp)
        world = world[~world["ADM0_A3_ISIN"].isin(["ANT"])] if "ADM0_A3_ISIN" in world else world
        merged = world.merge(panel, left_on="ISO_A3", right_on="iso3", how="left")
        fig, ax = plt.subplots(figsize=(12, 6))
        merged.plot(column="hazard_events_per_year", cmap="YlOrRd",
                    legend=True, ax=ax, missing_kwds={"color": "#eeeeee"},
                    linewidth=0.3, edgecolor="grey")
        ax.set_title("Figure 2 — Natural-hazard exposure: average recorded disaster "
                     "events per year, 2015–2024\n(Grey = no data. Source: EM-DAT via UN HDX)",
                     fontsize=11)
        ax.set_axis_off()
        fig.tight_layout()
        fig.savefig(FIGS / "fig2_map_hazard.png", dpi=150)
        plt.close(fig)
        return "map"
    except Exception as e:
        top = panel.nlargest(20, "hazard_events_per_year")
        fig, ax = plt.subplots(figsize=(9, 6))
        ax.barh(top["country"], top["hazard_events_per_year"], color="#fc8d59")
        ax.invert_yaxis()
        ax.set_xlabel("Average disaster events per year (2015–2024)")
        ax.set_title("Figure 2 (bar version) — Top 20 countries by hazard exposure\n"
                     "(install geopandas to render the map version)", fontsize=11)
        fig.tight_layout()
        fig.savefig(FIGS / "fig2_map_hazard.png", dpi=150)
        plt.close(fig)
        return "bars"


def fig3_scatter(panel):
    """Wealth vs child survival: the classic development story."""
    d = panel.dropna(subset=["gdp_per_capita", "under5_mortality"])
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.scatter(d["gdp_per_capita"], d["under5_mortality"],
               s=40, alpha=0.7, color="#2166ac", edgecolor="white")
    ax.set_xscale("log")
    ax.set_yscale("log")
    # simple log-log fit line to make the pattern explicit
    m = (d["gdp_per_capita"] > 0) & (d["under5_mortality"] > 0)
    b, a = np.polyfit(np.log10(d.loc[m, "gdp_per_capita"]),
                      np.log10(d.loc[m, "under5_mortality"]), 1)
    xs = np.logspace(np.log10(d["gdp_per_capita"].min()),
                     np.log10(d["gdp_per_capita"].max()), 50)
    ax.plot(xs, 10 ** (a + b * np.log10(xs)), "--", color="#b2182b", lw=2,
            label=f"log-log fit (slope={b:.2f})")
    for iso in ["AFG", "SOM", "TCD", "JPN", "NOR", "BRA", "IND", "NGA"]:
        r = d[d["iso3"] == iso]
        if len(r):
            ax.annotate(r["country"].iloc[0],
                        (r["gdp_per_capita"].iloc[0], r["under5_mortality"].iloc[0]),
                        fontsize=8, xytext=(4, 4), textcoords="offset points")
    ax.set_xlabel("GDP per capita, constant 2015 US$ (log scale)")
    ax.set_ylabel("Under-5 mortality per 1,000 births (log scale)")
    ax.set_title("Figure 3 — Poverty and child deaths move together (2015–2024 averages)\n"
                 "Each dot is a country. Source: World Bank Open Data", fontsize=11)
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGS / "fig3_scatter_gdp_mortality.png", dpi=150)
    plt.close(fig)


def fig4_top(panel):
    """Where do all these problems overlap? A short, memorable ranking."""
    cols = {"hazard_events_per_year": "Hazard exposure",
            "under5_mortality": "Child mortality",
            "undernourishment": "Undernourishment",
            "refugees_per_1000": "Refugees hosted"}
    ranks = panel.copy()
    for c in cols:
        ranks[c] = ranks[c].rank(pct=True, ascending=False)   # 1 = worst
    ranks["burden_score"] = ranks[list(cols)].mean(axis=1)
    top = ranks.nsmallest(15, "burden_score")
    fig, ax = plt.subplots(figsize=(9, 6))
    bottom = None
    colors = ["#4393c3", "#d6604d", "#f4a582", "#92c5de"]
    for c, col in zip(cols, colors):
        vals = top[c] / sum(top[c] for _ in cols) * top["burden_score"]
        ax.barh(top["country"], vals, left=bottom, color=col, label=cols[c])
        bottom = (vals if bottom is None else bottom + vals)
    ax.invert_yaxis()
    ax.set_xlabel("Composite vulnerability score (average percentile across factors; longer = more vulnerable)")
    ax.set_title("Figure 4 — Countries where several humanitarian factors overlap\n"
                 "(each colour is one factor's share of the score)", fontsize=11)
    ax.legend(ncol=2, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGS / "fig4_top_countries.png", dpi=150)
    plt.close(fig)
    ranks.nsmallest(20, "burden_score")[["country", "burden_score"]].to_csv(
        DATA / "vulnerability_ranking.csv", index=False)


if __name__ == "__main__":
    wb, em, dp = load()
    panel, yearly = build_panel(wb, em, dp)
    fig1_trends(em)
    kind = fig2_map(panel)
    fig3_scatter(panel)
    fig4_top(panel)
    corr = panel[["gdp_per_capita", "under5_mortality"]].dropna().corr().iloc[0, 1]
    print(f"\nKey numbers for the report:")
    print(f"- Pearson correlation GDP-per-capita vs under-5 mortality: {corr:.2f} "
          f"(on raw scales; strongly negative)")
    print(f"- Figure 2 rendered as: {kind}")
    print("Figures saved to ./figures/")
