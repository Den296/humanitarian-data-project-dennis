# 🌍 Humanitarian Data Science Project

**Quantifying what makes humanitarian crises worse — and who bears the burden.**

A reproducible, beginner-friendly data-science project built entirely on **open
United Nations–affiliated data**. It walks a student through the full lifecycle:
choosing factors → mapping them to indicators → ingesting real APIs (with
fallbacks for blocked downloads) → cleaning → statistical analysis → storytelling
visualisations.

---

## 1. The question

Humanitarian response is shaped by the interaction of **hazards**,
**vulnerability**, and **capacity to cope**. This project asks:

> *Which measurable factors best explain where humanitarian need concentrates,
> and how do they overlap across countries?*

We start from a broad factor list (natural hazards, conflict, displacement,
poverty, food security, health systems, climate, education/gender,
infrastructure, governance, demographics, funding) and select **four** that are
quantifiable, country-comparable, freely available, and span the chain
*trigger → impact → capacity*:

| Factor | Role | Metric used | Source |
|---|---|---|---|
| Natural-hazard exposure | trigger | disaster events/year; people affected per 100k | EM-DAT Country Profiles (CRED, WHO collaborating centre) via UN OCHA's [Humanitarian Data Exchange](https://data.humdata.org) |
| Forced displacement | impact | refugees hosted per 1,000 population | UNHCR Global Trends (mirrored via UNICEF SDMX API) |
| Economic capacity | coping ability | GDP per capita, constant 2015 US$ | World Bank Open Data (`NY.GDP.PCAP.KD`) |
| Health vulnerability | susceptibility | under-5 deaths per 1,000 births; % undernourished | World Bank (`SH.DYN.MORT`, `SN.ITK.DEFC.ZS`) |

**Design principle:** all rates are *per-capita*, so small countries are
compared fairly with large ones, and the panel keeps only sovereign states
(regional aggregates like "Sub-Saharan Africa" and data-sparse territories are
filtered out using the World Bank's own country registry).

## 2. Repository structure

```
humanitarian-data-project/
├── README.md                  ← this file: story-first introduction
├── requirements.txt           ← pinned-free dependency list
├── LICENSE                    ← MIT
├── data/
│   ├── SOURCES.md             ← dataset citations & retrieval dates
│   ├── worldbank_indicators.csv   raw WB panel (3,598 rows × 7 cols)
│   ├── emdat_events.csv           raw EM-DAT events (6,612 rows, 219 countries)
│   ├── displaced.csv              refugees per 1,000 pop (14,615 obs)
│   ├── real_countries.csv         sovereign-country registry (WB API)
│   ├── country_year_panel.csv     tidy long panel, one row per country×year
│   ├── country_snapshot.csv       decade-average snapshot per country
│   └── vulnerability_ranking.csv  composite burden score
├── src/
│   ├── fetch_data.py          ← ingestion: retry/backoff + graceful fallbacks
│   └── analyze.py             ← cleaning, statistics, figures (prints explanations)
└── figures/
    ├── fig1_trends.png            events vs people affected, 2000–2024
    ├── fig2_map_hazard.png        geography of hazard exposure (map or ranked bars)
    ├── fig3_scatter_gdp_mortality.png  wealth vs child survival (log-log)
    └── fig4_top_countries.png     composite vulnerability ranking
```

## 3. Quickstart

```bash
pip install -r requirements.txt
python src/fetch_data.py      # download the three public datasets (~2 min)
python src/analyze.py         # build panels, compute stats, render figures
```

Both scripts print step-by-step explanations, so a student can follow the logic
without prior data-science experience. If a source blocks automated access
(UNHCR's portal returns HTTP 403 to bots), `fetch_data.py` automatically falls
back to UNICEF's SDMX mirror of the same official UNHCR Global Trends series —
a deliberate lesson in building resilient pipelines.

## 4. Analysis methods (and why we chose them)

1. **Descriptive aggregation** — decade averages (2015–2024) per country keep
   the comparison stable against single extreme years.
2. **Rate normalisation** — affected per 100k, refugees per 1,000. Absolute
   counts would just rank countries by size.
3. **Correlation analysis** — Pearson on the raw scale gives r = **−0.46**, but
   on the log–log scale it strengthens to **−0.87** (Spearman agrees). Teaching
   moment: relationships between income and mortality are *multiplicative*, not
   linear — always look at your data on sensible scales before concluding.
4. **Log–log regression line** — fitted slope shows child mortality falls about
   an order of magnitude per order-of-magnitude increase in income.
5. **Composite index** — average percentile rank across the four factors
   ("burden score"). A gentle introduction to index construction; natural next
   steps are PCA or weighted indices (e.g., INFORM Severity).

## 5. Key findings produced by the pipeline

- **Hazard exposure concentrates geographically**: the United States, China,
  Indonesia and India top absolute event counts (Pacific Rim / South & East Asia).
- **Wealth and child survival move together**: log-log correlation −0.87
  (Figure 3); outliers invite discussion about governance and resource curses.
- **Displacement burden falls on relatively poor neighbours**, not wealthy
  nations: **Lebanon (117 refugees/1,000 people), Jordan (48), Türkiye (28)**
  lead the per-capita ranking (Figure 4 context).
- **Where factors overlap**: Uganda, DR Congo, Chad, South Sudan, Pakistan and
  Afghanistan head the composite vulnerability ranking.

## 6. Visualisations and the story each tells

| Figure | Type | Why it matters |
|---|---|---|
| Fig 1 — Trends | dual-axis time series | Asks "are disasters getting worse?" Separates event counts from human impact; surfaces reporting effects vs. genuine climate trends. |
| Fig 2 — Exposure map | choropleth (auto-falls back to ranked bars without geopandas) | Spatial patterns the eye catches instantly that tables hide; every country visible at once. |
| Fig 3 — Wealth vs child deaths | log-log scatter + fit, labelled countries | The central inequality story of development; annotated outliers spark classroom debate. |
| Fig 4 — Composite ranking | stacked-share bars | Shows multidimensional overlap that any single indicator misses; doubles as a prioritisation tool. |

Every figure leads with a plain-language takeaway title and cites its source —
the two habits that make analysis understandable to non-technical audiences.

## 7. Presenting this project to a broader audience

- **GitHub** — code plus committed cleaned CSVs (live APIs rate-limit/block, so
  committing data guarantees reproducibility); enable GitHub Pages for a
  one-page summary site.
- **Observable / Streamlit Cloud / Plotly Dash** — interactive maps where users
  hover countries and filter years (Plotly's choropleth means students never
  need GIS software).
- **Tableau Public** — a drag-and-drop twin of this analysis for non-programmers.
- Communication checklist: takeaway-first titles, direct annotation instead of
  legend hunting, source + retrieval date on every chart, one executive-summary
  slide (*4 factors → 4 numbers → 4 figures → 3 policy implications*).

## 8. Extending the project (student challenges)

1. Add the **conflict** factor via UCDP/PRIO battle-death data and test whether
   it improves the composite's predictive power.
2. Replace equal weights in the burden score with **PCA-derived weights**;
   compare rankings.
3. Join **ND-GAIN** climate-vulnerability scores and forecast 2030 hotspots.
4. Build a **Streamlit app**: pick a country, see its four factor gauges versus
   regional medians.
5. Write a one-page **policy brief** from Figure 4 — argue where marginal aid
   dollars save most lives.

## 9. Caveats (be honest about data)

- EM-DAT reflects **reported** disasters; coverage improved over time, so rising
  event counts partly measure better reporting.
- Refugee-per-1,000 uses host-country mid-year estimates; definitions of
  "refugee" vary slightly across agencies.
- World Bank indicators carry model-based uncertainty for fragile states —
  exactly the places where accuracy matters most.
- Correlation ≠ causation. These charts describe associations; causal claims
  need study designs beyond this repository's scope.

## License & data terms

Code: MIT (see `LICENSE`). Data remain owned by their sources; citations and
terms are listed in [`data/SOURCES.md`](data/SOURCES.md).
