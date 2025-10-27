from google.adk.agents.llm_agent import Agent
import requests
import json

# Tool implementation
def get_weather_forecast(city: str) -> dict:
    """Returns the weather forecast, including maximum wind speed and precipitation sum, for the next day in a specified city."""
    
    # First, get the latitude and longitude for the city.
    geocode_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1"
    response = requests.get(geocode_url)
    if response.status_code != 200:
        return {"status": "error", "message": "Could not get city coordinates."}
    
    geocode_data = response.json()
    if not geocode_data.get("results"):
        return {"status": "error", "message": f"Could not find coordinates for {city}."}

    latitude = geocode_data["results"][0]["latitude"]
    longitude = geocode_data["results"][0]["longitude"]

    # Now, get the weather forecast.
    # ADDED 'precipitation_sum' to the daily variables
    weather_url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&"
        f"daily=weathercode,temperature_2m_max,temperature_2m_min,wind_speed_10m_max,precipitation_sum&"
        f"timezone=auto&forecast_days=2"
    )
    response = requests.get(weather_url)
    if response.status_code != 200:
        return {"status": "error", "message": "Could not get weather forecast."}

    weather_data = response.json()
    
    # Extract tomorrow's forecast (index 1 is tomorrow)
    tomorrow_forecast = {
        "date": weather_data["daily"]["time"][1],
        "weathercode": weather_data["daily"]["weathercode"][1],
        "temperature_max": weather_data["daily"]["temperature_2m_max"][1],
        "temperature_min": weather_data["daily"]["temperature_2m_min"][1],
        "wind_speed_max": weather_data["daily"]["wind_speed_10m_max"][1],
        "wind_unit": weather_data["daily_units"]["wind_speed_10m_max"],
        # ADDED total precipitation sum for tomorrow
        "precipitation_sum": weather_data["daily"]["precipitation_sum"][1],
        "precipitation_unit": weather_data["daily_units"]["precipitation_sum"],
    }

    return {"status": "success", "city": city, "forecast": tomorrow_forecast}

root_agent = Agent(
    model='gemini-2.5-flash',
    name='root_agent',
    # Updated description to reflect all new capabilities
    description="Tells the weather forecast for the next day in a specified city, including wind strength and total precipitation.",
    instruction="You are a helpful assistant that tells the weather forecast. Use the 'get_weather_forecast' tool for this purpose.",
    tools=[get_weather_forecast],
)