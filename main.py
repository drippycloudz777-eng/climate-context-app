from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
from datetime import date

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

CITIES = {
    "San Rafael": {"lat": 37.9735, "lon": -122.5311, "noaa_station": "GHCND:USW00093228"},
    "Novato":     {"lat": 38.1074, "lon": -122.5697, "noaa_station": "GHCND:USC00046374"},
    "Mill Valley":{"lat": 37.9060, "lon": -122.5449, "noaa_station": "GHCND:USC00045534"},
}

NOAA_TOKEN = "pyrBwBPoRvRGfUlGgUKLddNxXwIXOuEu"
ALERT_THRESHOLD_F = 3

FALLBACK_RECORDS = {
    "San Rafael":  {"record_high": 73, "year": 2019},
    "Novato":      {"record_high": 76, "year": 2014},
    "Mill Valley": {"record_high": 70, "year": 2019},
}

def c_to_f(c): return c * 9 / 5 + 32

def fetch_forecast_high(lat, lon):
    r = requests.get("https://api.open-meteo.com/v1/forecast", params={
        "latitude": lat, "longitude": lon,
        "daily": "temperature_2m_max",
        "temperature_unit": "fahrenheit",
        "timezone": "America/Los_Angeles",
        "forecast_days": 1,
    }, timeout=10)
    return r.json()["daily"]["temperature_2m_max"][0]

def fetch_record_noaa(station_id):
    today = date.today()
    month_day = f"{today.month:02d}-{today.day:02d}"
    r = requests.get("https://www.ncdc.noaa.gov/cdo-web/api/v2/data",
        headers={"token": NOAA_TOKEN},
        params={
            "datasetid": "GHCND", "stationid": station_id,
            "datatypeid": "TMAX",
            "startdate": f"{today.year - 1}-{month_day}",
            "enddate":   f"{today.year - 1}-{month_day}",
            "units": "standard", "limit": 1,
        }, timeout=10)
    results = r.json().get("results", [])
    if results:
        return round(c_to_f(results[0]["value"] / 10), 1), int(results[0]["date"][:4])
    return None, None

def classify(forecasted, record):
    diff = record - forecasted
    if forecasted > record:   return "HISTORIC EVENT"
    if diff <= ALERT_THRESHOLD_F: return "CLIMATE ALERT"
    if diff <= 10:            return "WARM DAY"
    return "ALL CLEAR"

@app.get("/")
def root():
    return {"status": "Climate Context API is running"}

@app.get("/weather")
def get_weather():
    today = date.today()
    results = []
    for city, cfg in CITIES.items():
        try:
            forecasted = fetch_forecast_high(cfg["lat"], cfg["lon"])
            record, record_year = fetch_record_noaa(cfg["noaa_station"])
            if record is None:
                fb = FALLBACK_RECORDS[city]
                record, record_year = fb["record_high"], fb["year"]
            status = classify(forecasted, record)
            results.append({
                "city": city,
                "date": str(today),
                "forecasted_high": round(forecasted, 1),
                "record_high": record,
                "record_year": record_year,
                "difference": round(record - forecasted, 1),
                "status": status,
            })
        except Exception as e:
            results.append({"city": city, "error": str(e)})
    return {"results": results}
