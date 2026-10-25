# Data Sources & Citations

All datasets are open and free to download. Retrieved **2026-10-26** by
`src/fetch_data.py`. If you re-run the fetcher later, refresh the dates below.

## 1. World Bank Open Data → `worldbank_indicators.csv`, `real_countries.csv`
- API: `https://api.worldbank.org/v2/country/all/indicator/{CODE}?format=json&date=2010:2023`
- Indicators used:
  - `SH.DYN.MORT` — Probability of dying at age <5 years per 1,000 live births
  - `SP.POP.TOTL` — Population, total
  - `NY.GDP.PCAP.KD` — GDP per capita, constant 2015 US$
  - `SN.ITK.DEFC.ZS` — Prevalence of undernourishment (% of population)
- Country registry: `https://api.worldbank.org/v2/country` (used to exclude
  regional aggregates from analysis; see `real_countries.csv`).
- Terms: CC BY 4.0 (World Bank Open Data License).
- Citation: The World Bank. *World Development Indicators.*
  https://data.worldbank.org (accessed 2026-10-26).

## 2. EM-DAT Country Profiles (CRED, WHO Collaborating Centre) → `emdat_events.csv`
- Published on UN OCHA's **Humanitarian Data Exchange**:
  https://data.humdata.org/dataset/em-dat-country-profiles
- One row per (year × country × disaster type): events, affected, deaths,
  adjusted damage, 2000–present. Quantifies natural-hazard exposure.
- Terms: free for research/education with attribution; EM-DAT caveats on
  reporting bias apply (see README §9).
- Citation: CRED, *EM-DAT International Disaster Database*,
  www.emdat.be, Université catholique de Louvre, Brussels-Belgium
  (via UN HDX, accessed 2026-10-26).

## 3. Forced displacement → `displaced.csv`
- Primary target: UNHCR Population Data Portal
  (`https://www.unhcr.org/population/download/getData.php`). The portal blocks
  automated downloads (HTTP 403), so the fetcher falls back to:
- Fallback actually used: UNICEF SDMX API mirror of **UNHCR Global Trends**,
  series `MG_RFGS_CNTRY_ASYLM_PER1000` (asylum-seekers/refugees hosted per
  1,000 national population):
  `https://sdmx.data.unicef.org/ws/public/sdmxapi/rest/data/UNICEF,MG,1.0/.MG_RFGS_CNTRY_ASYLM_PER1000..?format=csv`
- Manual alternative: https://www.unhcr.org/refugee-statistics/
- Citation: UNHCR. *Global Trends — Refugee Statistics.*
  UNHCR Population Data Portal / UNICEF Data Watch (accessed 2026-10-26).

## Derived files (created by `src/analyze.py`)
| File | Contents |
|---|---|
| `country_year_panel.csv` | tidy long panel: one row per country × year |
| `country_snapshot.csv`   | 2015–2024 decade averages per sovereign country |
| `vulnerability_ranking.csv` | composite burden score (percentile average across factors) |

## Suggested future sources (README extension challenges)
- UCDP/PRIO Armed Conflict Dataset — https://ucdp.uu.se (conflict factor)
- ND-GAIN Country Index (Notre Dame) — climate vulnerability & readiness
- INFORM Severity index — https://drmkc.jrc.ec.europa.eu/inform-index
- UN OCHA Financial Tracking Service — humanitarian funding flows
- WorldPop / UN WPP — population denominators beyond WB totals
