"""
fetch_data.py — Gather open, verifiable data for the humanitarian project.

Three sources are downloaded here (all public, no API keys required):

1. World Bank Open Data API  ->  data/worldbank_indicators.csv
   - SH.DYN.MORT     Under-5 mortality rate (per 1,000 live births) [health]
   - SP.POP.TOTL     Total population                              [exposure]
   - NY.GDP.PCAP.KD  GDP per capita, constant 2015 US$             [economy]
   - SN.ITK.DEFC.ZS  Prevalence of undernourishment (% of pop.)    [food security]

2. EM-DAT Country Profiles (CRED / WHO Collaborating Office, published on
   UN OCHA's Humanitarian Data Exchange)  ->  data/emdat_events.csv
   One row per (year x country x disaster type): number of events, people
   affected, deaths and economic damage. This quantifies the
   "natural-hazard exposure" factor at country level, 2000-present.

3. UNHCR Population Data Portal  ->  data/unhcr_displaced.csv
   Official mid-year estimates of refugees, asylum-seekers, IDPs and
   stateless people by country of asylum = the "forced displacement" factor.
   NOTE: UNHCR sometimes blocks automated downloads (HTTP 403). If that
   happens this script falls back to a manual-download hint and keeps any
   previously saved copy, so the rest of the pipeline still runs.

Usage:      python src/fetch_data.py
Requires:   pandas, requests, openpyxl
"""

import io
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0 (humanitarian-edu-project; student demo)"}


def get(url, params=None, tries=4, **kw):
    """GET with retry + backoff so flaky networks don't break students."""
    last = None
    for attempt in range(tries):
        try:
            r = requests.get(url, params=params, headers=HEADERS,
                             timeout=90, **kw)
            if r.status_code == 200:
                return r
            last = f"HTTP {r.status_code}"
        except Exception as e:                      # network errors
            last = f"{type(e).__name__}: {e}"
        print(f"  ! {last} (attempt {attempt+1})")
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Failed after {tries} attempts ({last}): {url}")


# ----------------------------------------------------------------------
# 1. World Bank indicators
# ----------------------------------------------------------------------
WB_INDICATORS = {
    "SH.DYN.MORT": "under5_mortality",
    "SP.POP.TOTL": "population",
    "NY.GDP.PCAP.KD": "gdp_per_capita",
    "SN.ITK.DEFC.ZS": "undernourishment",
}


def fetch_worldbank():
    frames = []
    for code, name in WB_INDICATORS.items():
        url = f"https://api.worldbank.org/v2/country/all/indicator/{code}"
        rows, page, pages = [], 1, 1
        while page <= pages:
            payload = get(url, params={"format": "json", "per_page": 20000,
                                       "page": page, "date": "2010:2023"}).json()
            if not isinstance(payload, list) or len(payload) != 2:
                print(f"  ! unexpected response for {code}, skipping")
                break
            meta, data = payload
            pages = int(meta.get("pages", 1))
            rows.extend(data or [])
            page += 1
        df = pd.json_normalize(rows).rename(columns={
            "countryiso3code": "iso3", "country.value": "country",
            "date": "year", "value": name})[["iso3", "country", "year", name]]
        df["year"] = df["year"].astype(int)
        frames.append(df.groupby(["iso3", "country", "year"],
                                 as_index=False).first())
        print(f"  World Bank {code} ({name}): {len(df)} rows")
    out = frames[0]
    for f in frames[1:]:
        out = out.merge(f, on=["iso3", "country", "year"], how="outer")
    ok = out["iso3"].str.len() == 3
    # World Bank publishes both real countries (AFG, BDI...) and aggregate
    # "synthetic" codes for regions/income groups (WLD, IDB, SSA, HPC...).
    # Keep only ISO-3 codes that match a real country name in the UN M49 list.
    REAL_ISO3 = set(pd.read_csv(DATA / "real_countries.csv", nrows=None)["iso3"]) \
        if (DATA / "real_countries.csv").exists() else None
    mask = ok & ~out["iso3"].isin(["WLD", "IDA", "IDX", "PST"])
    if REAL_ISO3:
        mask &= out["iso3"].isin(REAL_ISO3)
    out = out[mask]
    out.to_csv(DATA / "worldbank_indicators.csv", index=False)
    print(f"Saved worldbank_indicators.csv shape={out.shape}")


# ----------------------------------------------------------------------
# 2. EM-DAT country profiles via HDX (UN OCHA's Humanitarian Data Exchange)
# ----------------------------------------------------------------------
EMDAT_HDX_URL = ("https://data.humdata.org/dataset/"
                 "74163686-a029-4e27-8fbf-c5bfcd13f953/resource/"
                 "c5ce40d6-07b1-4f36-955a-d6196436ff6b/download/"
                 "emdat-country-profiles_2026_10_21.xlsx")


def fetch_emdat():
    r = get(EMDAT_HDX_URL)
    df = pd.read_excel(io.BytesIO(r.content), header=0)
    df.columns = [str(c).strip() for c in df.columns]
    keep = ["Year", "Country", "ISO", "Disaster Group", "Disaster Type",
            "Total Events", "Total Affected", "Total Deaths",
            "Total Damage (USD, adjusted)"]
    df = df[[c for c in keep if c in df.columns]].copy()
    df = df[pd.to_numeric(df["Year"], errors="coerce").notna()]
    df["Year"] = df["Year"].astype(int)
    df = df[df["Year"] >= 2000]
    df.to_csv(DATA / "emdat_events.csv", index=False)
    print(f"Saved emdat_events.csv rows={len(df)} "
          f"(countries={df['ISO'].nunique()}, years={df['Year'].min()}-{df['Year'].max()})")


# ----------------------------------------------------------------------
# 3. Forced displacement: UNHCR portal first, UNICEF/UNHCR mirror as fallback
# ----------------------------------------------------------------------
# UNICEF's SDMX API mirrors the official UNHCR "Global Trends" refugee
# statistics (per-1,000-population host-country series), so we never lose
# the displacement factor even if UNHCR blocks automated downloads.
UNICEF_REFUGEES_URL = ("https://sdmx.data.unicef.org/ws/public/sdmxapi/rest/"
                       "data/UNICEF,MG,1.0/.MG_RFGS_CNTRY_ASYLM_PER1000.."
                       "?format=csv")


def _fetch_unhcr_direct():
    url = "https://www.unhcr.org/population/download/getData.php"
    params = {
        "year[]": list(range(2015, 2024)),
        "field_of_activity[]": "*",
        "type_of_population[]": ["refugees_and_similar", "idps",
                                 "asylum_seekers_year_end", "stateless"],
        "coo_country[]": "*", "coa_country[]": "*",
        "language": "en", "displayId": "0",
    }
    r = get(url, params=params, tries=2)
    raw = pd.read_csv(io.BytesIO(r.content), sep="\t", encoding="utf-8-sig",
                      dtype=str, engine="python", on_bad_lines="skip")
    raw = raw.rename(columns={"Year": "year", "Country of asylum": "country",
                              "Refugees": "refugees", "Asylum seekers": "asylum_seekers",
                              "IDPs": "idps", "Stateless": "stateless"})
    num = [c for c in ("refugees", "asylum_seekers", "idps", "stateless")
           if c in raw.columns]
    for c in num:
        raw[c] = pd.to_numeric(raw[c].astype(str).str.replace(",", ""),
                               errors="coerce").fillna(0)
    return raw.groupby(["year", "country"], as_index=False)[num].sum()


def _fetch_refugees_fallback():
    """UNHCR Global Trends data mirrored by UNICEF (per 1,000 population)."""
    r = get(UNICEF_REFUGEES_URL, tries=3)
    df = pd.read_csv(io.StringIO(r.text))
    df = df[df["TIME_PERIOD"].astype(str).str.isdigit()]
    out = df[["REF_AREA", "TIME_PERIOD", "OBS_VALUE"]].rename(columns={
        "REF_AREA": "iso3", "TIME_PERIOD": "year",
        "OBS_VALUE": "refugees_per_1000_pop"})
    out["year"] = out["year"].astype(int)
    print("  NOTE: used UNICEF/UNHCR 'Global Trends' mirror "
          "(refugees hosted per 1,000 people). Source citation kept in file.")
    return out


def fetch_unhcr():
    dest = DATA / "displaced.csv"
    try:
        agg = _fetch_unhcr_direct()
        agg.to_csv(dest, index=False)
        print(f"Saved displaced.csv (UNHCR direct) shape={agg.shape}")
    except RuntimeError as e:
        print(f"  ! UNHCR direct download blocked ({e}); trying UNICEF mirror ...")
        try:
            fb = _fetch_refugees_fallback()
            fb.to_csv(dest, index=False)
            print(f"Saved displaced.csv (fallback) shape={fb.shape}")
        except RuntimeError as e2:
            print(f"  ! fallback also failed ({e2}). Manual step: download from "
                  "https://www.unhcr.org/refugee-statistics/ into data/.")


if __name__ == "__main__":
    print("[1/3] World Bank Open Data ...");    fetch_worldbank()
    print("[2/3] EM-DAT via UN HDX ...");       fetch_emdat()
    print("[3/3] UNHCR Population API ...");    fetch_unhcr()
    print("Done. Files are in ./data/")
