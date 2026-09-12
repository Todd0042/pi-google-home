"""
Pi Google Home — Weather Skill
Live weather forecasts powered by Open-Meteo (Zero API key required).
"""

import requests
from typing import Optional

WMO_CODE_MAP = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "foggy",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    71: "slight snow fall",
    73: "moderate snow fall",
    75: "heavy snow fall",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    95: "thunderstorms",
}

def get_weather(location_name: Optional[str] = None) -> str:
    """
    Fetches real-time weather for a given city or auto-detected location.
    """
    try:
        # Default to IP geolocation if no location specified
        lat, lon, city_label = 30.2672, -97.7431, "Austin, Texas"

        if location_name:
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={requests.utils.quote(location_name)}&count=1&language=en&format=json"
            geo_res = requests.get(geo_url, timeout=5).json()
            if "results" in geo_res and len(geo_res["results"]) > 0:
                top = geo_res["results"][0]
                lat = top["latitude"]
                lon = top["longitude"]
                city_label = f"{top['name']}"
                if "admin1" in top and top["admin1"]:
                    city_label += f", {top['admin1']}"
            else:
                return f"I couldn't find the location for {location_name}."
        else:
            # Quick IP lookup
            try:
                ip_res = requests.get("https://ipapi.co/json/", timeout=3).json()
                if "latitude" in ip_res:
                    lat = ip_res["latitude"]
                    lon = ip_res["longitude"]
                    city_label = f"{ip_res.get('city', 'your area')}"
            except Exception:
                pass

        url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m"
            "&temperature_unit=fahrenheit&wind_speed_unit=mph"
        )
        res = requests.get(url, timeout=5).json()
        curr = res.get("current", {})
        temp = round(curr.get("temperature_2m", 70))
        feels_like = round(curr.get("apparent_temperature", temp))
        wind = round(curr.get("wind_speed_10m", 0))
        code = curr.get("weather_code", 0)
        condition = WMO_CODE_MAP.get(code, "fair")

        return f"In {city_label}, it's currently {temp} degrees and {condition}, with winds at {wind} miles per hour."

    except Exception as e:
        print(f"[ERROR] Weather lookup failed: {e}")
        return "I'm having trouble fetching the weather right now."

if __name__ == "__main__":
    print(get_weather("New York"))
    print(get_weather("London"))
    print(get_weather())
