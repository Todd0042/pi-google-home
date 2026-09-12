"""
Pi Google Home — Weather Skill
Live weather forecasts powered by Open-Meteo (Zero API key required)
with automatic IP geolocation discovery and caching.
"""

import os
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

# Cached auto-detected local coordinates
_CACHED_LOCATION = None

def detect_home_location() -> tuple[float, float, str]:
    """
    Auto-detects the user's home location using public IP geolocation.
    Returns: (latitude, longitude, city_label)
    """
    global _CACHED_LOCATION
    if _CACHED_LOCATION:
        return _CACHED_LOCATION

    # 1. Check user override in environment
    env_city = os.getenv("HOME_CITY")
    if env_city:
        try:
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={requests.utils.quote(env_city)}&count=1&language=en&format=json"
            geo = requests.get(geo_url, timeout=4).json()
            if "results" in geo and geo["results"]:
                top = geo["results"][0]
                _CACHED_LOCATION = (top["latitude"], top["longitude"], f"{top['name']}, {top.get('admin1', '')}")
                return _CACHED_LOCATION
        except Exception:
            pass

    # 2. Try ip-api.com
    try:
        res = requests.get("http://ip-api.com/json/", timeout=4).json()
        if res.get("status") == "success":
            city = res.get("city", "")
            region = res.get("regionName", "")
            label = f"{city}, {region}" if city else "your area"
            _CACHED_LOCATION = (float(res["lat"]), float(res["lon"]), label)
            print(f"==> Auto-detected home location: {_CACHED_LOCATION[2]} ({_CACHED_LOCATION[0]}, {_CACHED_LOCATION[1]})")
            return _CACHED_LOCATION
    except Exception:
        pass

    # 3. Fallback to ipinfo.io
    try:
        res = requests.get("https://ipinfo.io/json", timeout=4).json()
        if "loc" in res:
            parts = res["loc"].split(",")
            city = res.get("city", "")
            region = res.get("region", "")
            label = f"{city}, {region}" if city else "your area"
            _CACHED_LOCATION = (float(parts[0]), float(parts[1]), label)
            return _CACHED_LOCATION
    except Exception:
        pass

    # Safe fallback
    return (30.2851, -81.8217, "Jacksonville, Florida")

def get_weather_context(location_name: Optional[str] = None) -> str:
    """
    Fetches real-time weather and a multi-day forecast from Open-Meteo,
    returning a structured summary string for Gemini to reason over.
    """
    try:
        import datetime
        if location_name and location_name.strip():
            clean_loc = location_name.strip().title()
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={requests.utils.quote(clean_loc)}&count=1&language=en&format=json"
            geo_res = requests.get(geo_url, timeout=4).json()
            if "results" in geo_res and len(geo_res["results"]) > 0:
                top = geo_res["results"][0]
                lat = top["latitude"]
                lon = top["longitude"]
                city_label = f"{top['name']}"
                if "admin1" in top and top["admin1"]:
                    city_label += f", {top['admin1']}"
            else:
                return f"Location '{location_name}' could not be resolved."
        else:
            lat, lon, city_label = detect_home_location()

        url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m"
            "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code"
            "&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=auto"
        )
        res = requests.get(url, timeout=4).json()
        curr = res.get("current", {})
        daily = res.get("daily", {})

        curr_temp = round(curr.get("temperature_2m", 70))
        feels_like = round(curr.get("apparent_temperature", curr_temp))
        wind = round(curr.get("wind_speed_10m", 0))
        code = curr.get("weather_code", 0)
        curr_condition = WMO_CODE_MAP.get(code, "fair")

        lines = [
            f"Location: {city_label}",
            f"Current: {curr_temp}°F (feels like {feels_like}°F), {curr_condition}, wind {wind} mph, precipitation {curr.get('precipitation', 0)} in",
            "Forecast:"
        ]

        times = daily.get("time", [])
        highs = daily.get("temperature_2m_max", [])
        lows = daily.get("temperature_2m_min", [])
        rain_probs = daily.get("precipitation_probability_max", [])
        codes = daily.get("weather_code", [])

        for i in range(min(6, len(times))):
            date_str = times[i]
            dt = datetime.date.fromisoformat(date_str)
            if i == 0:
                day_name = f"Today ({dt.strftime('%A, %b %d')})"
            elif i == 1:
                day_name = f"Tomorrow ({dt.strftime('%A, %b %d')})"
            else:
                day_name = dt.strftime("%A, %b %d")

            h = round(highs[i]) if i < len(highs) else curr_temp
            l = round(lows[i]) if i < len(lows) else curr_temp
            r = rain_probs[i] if i < len(rain_probs) else 0
            c = WMO_CODE_MAP.get(codes[i], "fair") if i < len(codes) else "fair"
            lines.append(f"- {day_name}: High {h}°F, Low {l}°F, {c}, {r}% chance of rain")

        return "\n".join(lines)

    except Exception as e:
        print(f"[WARN] Failed to fetch weather context: {e}")
        return ""

def get_weather(location_name: Optional[str] = None, query: Optional[str] = None) -> str:
    """
    Fetches real-time weather and daily forecast for a given city or auto-detected home location.
    """
    try:
        if location_name and location_name.strip():
            clean_loc = location_name.strip().title()
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={requests.utils.quote(clean_loc)}&count=1&language=en&format=json"
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
            # Automatically use the detected home location
            lat, lon, city_label = detect_home_location()

        url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m"
            "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max"
            "&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=auto"
        )
        res = requests.get(url, timeout=5).json()
        curr = res.get("current", {})
        daily = res.get("daily", {})

        temp = round(curr.get("temperature_2m", 70))
        feels_like = round(curr.get("apparent_temperature", temp))
        wind = round(curr.get("wind_speed_10m", 0))
        code = curr.get("weather_code", 0)
        condition = WMO_CODE_MAP.get(code, "fair")

        high = round(daily.get("temperature_2m_max", [temp])[0])
        low = round(daily.get("temperature_2m_min", [temp])[0])
        rain_prob = daily.get("precipitation_probability_max", [0])[0]

        q = (query or "").lower()

        # Specific rain query
        if "rain" in q:
            if curr.get("precipitation", 0) > 0:
                return f"It is currently raining in {city_label}. Today has a {rain_prob} percent chance of rain with a high of {high} degrees."
            elif rain_prob > 30:
                return f"In {city_label}, there is a {rain_prob} percent chance of rain today with a high of {high} and low of {low}."
            else:
                return f"It doesn't look like it will rain today in {city_label}. The chance of rain is only {rain_prob} percent."

        # Specific temp query
        if any(w in q for w in ["temperature", "how hot", "how cold"]):
            feels_str = f", feeling like {feels_like}," if abs(feels_like - temp) >= 4 else ""
            return f"In {city_label}, it's currently {temp} degrees{feels_str} with an expected high of {high} and low of {low}."

        # General forecast response
        feels_str = f" that feels like {feels_like}" if abs(feels_like - temp) >= 4 else ""
        msg = f"In {city_label}, it's currently {temp} degrees{feels_str} and {condition}. Today's forecast has a high of {high} and a low of {low}."
        if rain_prob >= 25:
            msg += f" There is a {rain_prob} percent chance of rain."
        return msg

    except Exception as e:
        print(f"[ERROR] Weather lookup failed: {e}")
        return "I'm having trouble fetching the weather right now."

def map_weather_icon(code: int, is_day: bool = True) -> str:
    """Returns an icon name identifier for the given WMO weather code."""
    if code in (0, 1):
        return "clear-day" if is_day else "clear-night"
    elif code in (2, 3):
        return "partly-cloudy-day" if is_day else "partly-cloudy-night"
    elif code in (45, 48):
        return "fog"
    elif code in (51, 53, 55):
        return "drizzle"
    elif code in (61, 63, 65, 80, 81, 82):
        return "rain"
    elif code in (71, 73, 75, 85, 86):
        return "snow"
    elif code in (95, 96, 99):
        return "thunderstorm"
    return "cloudy"

def get_wind_direction_label(degrees: float) -> str:
    directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    idx = round(degrees / (360.0 / len(directions))) % len(directions)
    return directions[idx]

def get_weather_display_data(location_name: Optional[str] = None) -> dict:
    """
    Fetches comprehensive real-time conditions and 7-day forecast
    formatted for the Smart Display frontend.
    """
    import datetime
    try:
        if location_name and location_name.strip():
            clean_loc = location_name.strip().title()
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={requests.utils.quote(clean_loc)}&count=1&language=en&format=json"
            geo_res = requests.get(geo_url, timeout=4).json()
            if "results" in geo_res and len(geo_res["results"]) > 0:
                top = geo_res["results"][0]
                lat = top["latitude"]
                lon = top["longitude"]
                city_label = f"{top['name']}"
                if "admin1" in top and top["admin1"]:
                    city_label += f", {top['admin1']}"
            else:
                lat, lon, city_label = detect_home_location()
        else:
            lat, lon, city_label = detect_home_location()

        url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,wind_direction_10m,surface_pressure,uv_index"
            "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code,uv_index_max,sunrise,sunset"
            "&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=auto"
        )
        res = requests.get(url, timeout=5).json()
        curr = res.get("current", {})
        daily = res.get("daily", {})

        curr_temp = round(curr.get("temperature_2m", 70))
        feels_like = round(curr.get("apparent_temperature", curr_temp))
        wind_speed = round(curr.get("wind_speed_10m", 0))
        wind_dir = get_wind_direction_label(curr.get("wind_direction_10m", 0))
        humidity = round(curr.get("relative_humidity_2m", 50))
        pressure = round(curr.get("surface_pressure", 1013))
        uv = round(curr.get("uv_index", 0), 1)
        precip = curr.get("precipitation", 0.0)
        code = curr.get("weather_code", 0)
        condition_name = WMO_CODE_MAP.get(code, "Fair").title()

        daily_times = daily.get("time", [])
        daily_highs = daily.get("temperature_2m_max", [])
        daily_lows = daily.get("temperature_2m_min", [])
        daily_rains = daily.get("precipitation_probability_max", [])
        daily_codes = daily.get("weather_code", [])

        today_high = round(daily_highs[0]) if daily_highs else curr_temp
        today_low = round(daily_lows[0]) if daily_lows else curr_temp
        today_rain_prob = daily_rains[0] if daily_rains else 0

        days_list = []
        for i in range(len(daily_times)):
            d_str = daily_times[i]
            dt = datetime.date.fromisoformat(d_str)
            if i == 0:
                name = "Today"
            elif i == 1:
                name = "Tomorrow"
            else:
                name = dt.strftime("%A")
            short_name = "Today" if i == 0 else dt.strftime("%a")
            d_code = daily_codes[i] if i < len(daily_codes) else 0
            d_high = round(daily_highs[i]) if i < len(daily_highs) else curr_temp
            d_low = round(daily_lows[i]) if i < len(daily_lows) else curr_temp
            d_rain = daily_rains[i] if i < len(daily_rains) else 0
            d_cond = WMO_CODE_MAP.get(d_code, "Fair").title()

            days_list.append({
                "date": d_str,
                "day_name": name,
                "short_name": short_name,
                "high": d_high,
                "low": d_low,
                "rain_prob": d_rain,
                "condition": d_cond,
                "code": d_code,
                "icon": map_weather_icon(d_code, is_day=True),
            })

        return {
            "success": True,
            "location": city_label,
            "current": {
                "temp": curr_temp,
                "feels_like": feels_like,
                "high": today_high,
                "low": today_low,
                "condition": condition_name,
                "code": code,
                "icon": map_weather_icon(code, is_day=True),
                "humidity": humidity,
                "wind_speed": wind_speed,
                "wind_direction": wind_dir,
                "pressure": pressure,
                "uv_index": uv,
                "precipitation": precip,
                "rain_prob": today_rain_prob,
            },
            "daily": days_list,
        }
    except Exception as e:
        print(f"[ERROR] Failed to compile display weather data: {e}")
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    print("Auto-detected local weather:")
    print(get_weather())
    print("\nDisplay weather JSON:")
    import json
    print(json.dumps(get_weather_display_data(), indent=2))
