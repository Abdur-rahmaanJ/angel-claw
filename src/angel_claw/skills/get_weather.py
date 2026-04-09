from angel_claw.skills.manager import skill
from angel_claw.utils import get_user_root
import json
import os

# Skill configuration - declare required fields
SKILL_CONFIG = {
    "fields": [
        {
            "name": "OPENWEATHER_API_KEY",
            "type": "password",
            "description": "API key from openweathermap.org",
        }
    ]
}


def _get_user_config(user_id):
    user_root = get_user_root(user_id)
    config_file = user_root / "skill_config.json"
    if config_file.exists():
        try:
            return json.load(open(config_file))
        except:
            pass
    return {}


@skill
def get_weather(city: str, units: str = "metric", user_id: str = None) -> str:
    """Returns weather for the specified city. Requires OPENWEATHER_API_KEY in skill config."""
    if user_id:
        config = _get_user_config(user_id)
        api_key = (
            config.get("get_weather", {}).get("fields", {}).get("OPENWEATHER_API_KEY")
        )
        if not api_key:
            return "Error: Please configure OPENWEATHER_API_KEY in Skills settings."
    else:
        api_key = None

    # If no API key, return mock data
    if not api_key:
        temperature = "20°C" if units == "metric" else "68°F"
        description = "Partly cloudy"
        return f"Weather for {city}: {description}, {temperature} ({units} units) [Demo - add API key for real data]"

    import requests

    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&units={units}&appid={api_key}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 401:
            return "Error: Invalid OpenWeather API key. Please check your config."
        data = resp.json()
        temp = data["main"]["temp"]
        desc = data["weather"][0]["description"]
        return f"Weather for {city}: {desc}, {temp}° ({units} units)"
    except Exception as e:
        return f"Error getting weather: {str(e)}"
