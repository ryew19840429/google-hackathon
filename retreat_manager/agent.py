from google.adk.agents.llm_agent import Agent
import requests
import json

# ---------------------------
# Tool 1: Weather forecast tool
# ---------------------------

def get_weather_forecast(city: str) -> dict:
    """
    Returns the weather forecast, including max wind speed and total precipitation,
    for the next day (tomorrow) in a specified city.

    Steps:
    1. Geocode city -> lat/lon
    2. Query Open-Meteo forecast for today and tomorrow
    3. Return tomorrow's forecast (index 1 in the daily arrays)
    """

    # 1. Get lat/lon of the city
    geocode_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1"
    response = requests.get(geocode_url)
    if response.status_code != 200:
        return {
            "status": "error",
            "message": "Could not get city coordinates."
        }

    geocode_data = response.json()
    if not geocode_data.get("results"):
        return {
            "status": "error",
            "message": f"Could not find coordinates for {city}."
        }

    latitude = geocode_data["results"][0]["latitude"]
    longitude = geocode_data["results"][0]["longitude"]

    # 2. Get weather forecast (today + tomorrow)
    # - temperature_2m_max/min: °C
    # - wind_speed_10m_max: maximum wind speed at 10m height (m/s)
    # - precipitation_sum: total precipitation accumulated over the day (mm)
    # forecast_days=2 -> index 0 = today, index 1 = tomorrow
    weather_url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={latitude}&longitude={longitude}&"
        f"daily=weathercode,temperature_2m_max,temperature_2m_min,"
        f"wind_speed_10m_max,precipitation_sum&"
        f"timezone=auto&forecast_days=2"
    )

    response = requests.get(weather_url)
    if response.status_code != 200:
        return {
            "status": "error",
            "message": "Could not get weather forecast."
        }

    weather_data = response.json()

    # 3. Extract tomorrow's forecast (index 1)
    # NOTE:
    #   - wind_speed_10m_max is in m/s
    #   - precipitation_sum is in mm for the full day
    #   - date is ISO YYYY-MM-DD
    try:
        tomorrow_forecast = {
            "date": weather_data["daily"]["time"][1],
            "weathercode": weather_data["daily"]["weathercode"][1],
            "temperature_max_c": weather_data["daily"]["temperature_2m_max"][1],
            "temperature_min_c": weather_data["daily"]["temperature_2m_min"][1],
            "wind_speed_max": weather_data["daily"]["wind_speed_10m_max"][1],
            "wind_speed_unit": weather_data["daily_units"]["wind_speed_10m_max"],
            "precipitation_sum": weather_data["daily"]["precipitation_sum"][1],
            "precipitation_unit": weather_data["daily_units"]["precipitation_sum"],
        }
    except (KeyError, IndexError):
        return {
            "status": "error",
            "message": "Forecast for tomorrow is not available."
        }

    return {
        "status": "success",
        "city": city,
        "forecast": tomorrow_forecast
    }


# ---------------------------
# Agent definition
# ---------------------------

root_agent = Agent(
    model="gemini-2.5-flash",
    name="root_agent",
    description=(
        "Event Setup Assistant that helps an organizer plan an event, "
        "checks weather for safety and suitability, proposes viable activities, "
        "and outputs a final structured event profile for further automation."
    ),
    instruction=(
        # --- Your final prompt merged here ---
        "You are an experienced Online Marketing manager and are currently asked to "
        "fulfill a role as an Event Setup Assistant.\n\n"

        "Your job is to help the event organizer define an event plan that is feasible, "
        "safe, and aligned with budget. You will:\n\n"

        "1. Collect required planning inputs from the organizer:\n"
        "   - City of the event\n"
        "   - Event date (specify the date as \"DD-MM-YYYY\")\n"
        "   - Expected number of participants\n"
        "   - Time of day (Morning / Afternoon / Evening)\n"
        "   - Target age group (e.g. \"students\", \"25–40 professionals\", \"families\")\n"
        "   - Cultural region of the audience (e.g. \"Local Dutch people\", "
        "\"Internationals in the Netherlands\", \"Mixed European professionals\")\n"
        "   - Budget range per person in EUR (specified format e.g.,: \"10–25 EUR\" or \"€10–25\").\n\n"

        "2. After collecting city and date, CALL the weather tool "
        "('get_weather_forecast') to get forecast categories "
        "(temperature range, rain/dry via precipitation_sum, wind strength via wind_speed_max).\n\n"

        "3. Based on the forecast result, CALL the event-finder tool to get a short list "
        "of suitable activity types and real candidate venues in that city. "
        "If the event-finder tool is not available yet, ask the organizer which "
        "activity type they prefer from the weather-safe options you can infer "
        "from the forecast (e.g. indoor vs outdoor).\n\n"

        "4. Ask the organizer to choose one final activity type / venue from that list.\n\n"

        "Once the organizer confirms the activity type, produce a FINAL EVENT PROFILE as compact JSON:\n\n"
        "{\n"
        "  \"city\": \"...\",\n"
        "  \"date\": \"...\",\n"
        "  \"season\": \"...\",\n"
        "  \"time_of_day\": \"...\",\n"
        "  \"participants\": 0,\n"
        "  \"culture_region\": \"...\",\n"
        "  \"target_age_group\": \"...\",\n"
        "  \"budget_range_per_person\": \"...\",\n"
        "  \"platform\": \"...\",\n"
        "  \"activity_type\": \"...\",\n"
        "  \"venue\": \"...\",\n"
        "  \"weather_context\": \"Rainy and windy evening, indoor recommended\"\n"
        "}\n\n"

        "IMPORTANT:\n"
        "- Do not generate any marketing images yourself.\n"
        "- Do not generate captions.\n"
        "- Do not style or beautify the text.\n"
        "- Your only job is to output the final JSON once the organizer "
        "confirms the activity_type and venue.\n\n"

        "After you output the final JSON, stop.\n\n"

        "Do not invent information. If the user is unsure, suggest likely defaults "
        "(for example: use tomorrow’s date, or infer season from month)."
    ),
    tools=[get_weather_forecast]  # later: add event_finder_tool here as well
)
