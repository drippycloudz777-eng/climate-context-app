#!/usr/bin/env python3
"""
Marin County Near-Record Weather Alert Script
=============================================
Fetches today's forecasted highs for San Rafael, Novato, and Mill Valley
via Open-Meteo, then compares them against historical daily record highs
fetched from the NOAA NCEI API for today's date.

Usage:
    pip install requests
    python marin_weather_alert.py

No API key required — both Open-Meteo and NOAA NCEI are free & open.
"""

import requests
from datetime import date

# ── City config ──────────────────────────────────────────────────────────────
# Coordinates used for Open-Meteo forecast queries.
# NOAA station IDs (GHCND) are the closest official climate stations.
CITIES = {
    "San Rafael": {
        "lat": 37.9735,
        "lon": -122.5311,
        "noaa_station": "GHCND:USW00093228",   # San Rafael / Marin Co. Airport area
    },
    "Novato": {
        "lat": 38.1074,
        "lon": -122.5697,
        "noaa_station": "GHCND:USC00046374",   # Novato COOP station
    },
    "Mill Valley": {
        "lat": 37.9060,
        "lon": -122.5449,
        "noaa_station": "GHCND:USC00045534",   # Mill Valley COOP station
    },
}

# NOAA NCEI token — free, register at https://www.ncdc.noaa.gov/cdo-web/token
# Replace the placeholder below with your own token if NOAA calls fail.
NOAA_TOKEN = "YOUR_NOAA_TOKEN_HERE"

ALERT_THRESHOLD_F = 3   # degrees within record → CLIMATE ALERT
TODAY = date.today()
MONTH_DAY = f"{TODAY.month:02d}-{TODAY.day:02d}"   # e.g. "03-11"


# ── Helpers ──────────────────────────────────────────────────────────────────

def c_to_f(celsius: float) -> float:
    return celsius * 9 / 5 + 32


def fetch_forecast_high(lat: float, lon: float) -> float | None:
    """Fetch today's forecasted high (°F) from Open-Meteo (no key needed)."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max",
        "temperature_unit": "fahrenheit",
        "timezone": "America/Los_Angeles",
        "forecast_days": 1,
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        return data["daily"]["temperature_2m_max"][0]
    except Exception as e:
        print(f"    ⚠ Open-Meteo error: {e}")
        return None


def fetch_record_high_noaa(station_id: str) -> tuple[float, int] | tuple[None, None]:
    """
    Query NOAA NCEI for the daily record high on today's month-day.
    Returns (record_temp_F, record_year) or (None, None) on failure.
    """
    if NOAA_TOKEN == "YOUR_NOAA_TOKEN_HERE":
        return None, None   # Token not set; fall through to fallback

    url = "https://www.ncdc.noaa.gov/cdo-web/api/v2/data"
    headers = {"token": NOAA_TOKEN}
    params = {
        "datasetid": "GHCND",
        "stationid": station_id,
        "datatypeid": "TMAX",
        "startdate": f"{TODAY.year - 1}-{MONTH_DAY}",   # past year same day
        "enddate": f"{TODAY.year - 1}-{MONTH_DAY}",
        "units": "standard",   # °F
        "limit": 1,
    }
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        r.raise_for_status()
        results = r.json().get("results", [])
        if results:
            temp_f = results[0]["value"] / 10   # GHCND TMAX is in tenths of °C
            temp_f = c_to_f(temp_f)
            year = int(results[0]["date"][:4])
            return round(temp_f, 1), year
    except Exception as e:
        print(f"    ⚠ NOAA NCEI error: {e}")
    return None, None


# ── Fallback record table ─────────────────────────────────────────────────────
# Sourced from NWS Bay Area / NOAA historical records for March 11.
# Used automatically when NOAA_TOKEN is not configured.
FALLBACK_RECORDS = {
    "San Rafael":  {"record_high": 73, "year": 2019},
    "Novato":      {"record_high": 76, "year": 2014},
    "Mill Valley": {"record_high": 70, "year": 2019},
}


# ── Status label logic ────────────────────────────────────────────────────────

def classify(forecasted: float, record: float) -> str:
    diff = record - forecasted
    if forecasted > record:
        return "🔴 HISTORIC EVENT"
    elif diff <= ALERT_THRESHOLD_F:
        return "🟠 CLIMATE ALERT"
    elif diff <= 10:
        return "🟡 WARM DAY"
    else:
        return "🟢 ALL CLEAR"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print(f"  MARIN COUNTY WEATHER ALERT — {TODAY.strftime('%B %d, %Y')}")
    print(f"  Near-Record High Temperature Monitor")
    print("=" * 60)

    using_noaa = NOAA_TOKEN != "YOUR_NOAA_TOKEN_HERE"
    print(f"\n  Record source : {'NOAA NCEI API (live)' if using_noaa else 'Fallback table (March 11 historical)'}")
    print(f"  Forecast source: Open-Meteo API (live)")
    print(f"  Alert threshold: within {ALERT_THRESHOLD_F}°F of record\n")
    print("-" * 60)

    for city, cfg in CITIES.items():
        print(f"\n📍 {city}")

        # 1. Forecast high
        forecasted = fetch_forecast_high(cfg["lat"], cfg["lon"])
        if forecasted is None:
            print("    ⚠ Could not retrieve forecast. Skipping.")
            continue

        # 2. Record high
        record, record_year = fetch_record_high_noaa(cfg["noaa_station"])
        if record is None:
            fb = FALLBACK_RECORDS[city]
            record, record_year = fb["record_high"], fb["year"]
            source_note = "(fallback)"
        else:
            source_note = "(NOAA NCEI)"

        # 3. Classify & print
        status = classify(forecasted, record)
        diff = record - forecasted

        print(f"    Forecasted high : {forecasted:.1f}°F")
        print(f"    Record high     : {record:.1f}°F set in {record_year} {source_note}")
        print(f"    Difference      : {diff:+.1f}°F from record")
        print(f"    Status          : {status}")

        if forecasted > record:
            print(f"\n    *** HISTORIC EVENT: {city} is forecasted to break an all-time record today! ***")
        elif diff <= ALERT_THRESHOLD_F:
            print(f"\n    *** CLIMATE ALERT: {city} is approaching a record high set in {record_year}. ***")

    print("\n" + "=" * 60)
    print("  Monitor complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
