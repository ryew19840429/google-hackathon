# %% [markdown]
# # Event Decision Agent Notebook
# 
# This notebook defines an AI agent that:
# 1. Gets weather info (mocked).
# 2. Classifies temperature / precipitation.
# 3. Recommends suitable event types (outdoor / indoor / online).
# 4. Explains the decision in natural language.
#
# The agent is built using google.adk.agents.llm_agent.Agent style.

# %%
# Imports
from typing import Dict, List
from google.adk.agents.llm_agent import Agent

# %% [markdown]
# ## 1. Activity mapping logic
# We map (Temperature category, Rain category) → Recommended activities.

# %%
weather_activity_mapping = [ 
    {"temp": "Hot", "rain": "Dry", "activities": ["Outdoor sports", "Barbecue", "Music festival"],
     "rationale": "High temperature and almost no rain allow for large outdoor gatherings."},

    {"temp": "Hot", "rain": "Rainy", "activities": ["Indoor exhibition", "Cinema", "Indoor gym", "Coffee meetup"],
     "rationale": "It is warm but rainy, so indoor social / leisure activities are more reliable."},

    {"temp": "Mild", "rain": "Dry", "activities": ["Park activities", "Team building exercises", "Outdoor workshop"],
     "rationale": "Comfortable temperature and dry conditions are ideal for light outdoor group activities."},

    {"temp": "Mild", "rain": "Rainy", "activities": ["Indoor workshop", "Small conference", "Indoor recreation"],
     "rationale": "Temperature is fine, but rain suggests moving to sheltered/indoor venues."},

    {"temp": "Cold", "rain": "Dry", "activities": ["Indoor meeting", "Training session", "Museum visit", "Greenhouse event"],
     "rationale": "Low temperature discourages outdoor time; indoor cultural or training events work well."},

    {"temp": "Cold", "rain": "Rainy", "activities": ["Online webinar", "Remote event", "Home interactive game night"],
     "rationale": "Cold and rainy is discouraging for travel; remote/online formats minimize risk and drop-out."}
]

# %% [markdown]
# Helper functions:
# - classify_temp: numeric °C → Hot / Mild / Cold
# - classify_rain: numeric mm → Dry / Rainy
# - recommend_activities: returns the matching rule row

# %%
def classify_temp(temp_c: float) -> str:
    """Classify a temperature (°C) into Hot / Mild / Cold."""
    if temp_c > 25:
        return "Hot"
    elif temp_c > 10:
        return "Mild"
    else:
        return "Cold"


def classify_rain(rain_mm: float) -> str:
    """Classify precipitation (mm) into Dry / Rainy."""
    if rain_mm < 1:
        return "Dry"
    else:
        return "Rainy"


def lookup_activity_rule(temp_cat: str, rain_cat: str) -> Dict:
    """Return the mapping row for (temp_cat, rain_cat)."""
    for row in weather_activity_mapping:
        if row["temp"] == temp_cat and row["rain"] == rain_cat:
            return row
    # fallback if nothing matches
    return {
        "temp": temp_cat,
        "rain": rain_cat,
        "activities": [],
        "rationale": "No rule found."
    }


def recommend_activities(temp_c: float, rain_mm: float) -> Dict:
    """
    Given numeric forecast inputs, return:
    - temp_category
    - rain_category
    - suggested activities
    - rationale
    """
    tcat = classify_temp(temp_c)
    rcat = classify_rain(rain_mm)
    rule = lookup_activity_rule(tcat, rcat)
    return {
        "temp_category": tcat,
        "rain_category": rcat,
        "activities": rule["activities"],
        "rationale": rule["rationale"],
        "extracted_inputs": {
            "temperature_c": temp_c,
            "rain_mm": rain_mm
        }
    }

# Quick smoke test
print(recommend_activities(28, 0.2))
print(recommend_activities(12, 3.5))
print(recommend_activities(4, 5.0))

# %% [markdown]
# ## 2. Mock tool functions (to be exposed to the agent)
# 
# In Google ADK style, tools are normal Python callables.
# We'll expose two tools:
# 
# 1. `get_current_time(city: str)`  
#    - Your original example, kept for backward compatibility / demo.
#
# 2. `get_weather_and_recommend(city: str, date: str)`  
#    - Returns forecasted temperature and precipitation (mocked here),
#      plus recommended activity types for that weather.
#
# In a real system, `get_weather_and_recommend` would:
# - call a weather API (e.g. Open-Meteo / Google Weather / internal service)
# - feed temp & rain into `recommend_activities`
# - return a structured dict

# %%
def get_current_time(city: str) -> dict:
    """Returns the current time in a specified city.
    (Mock implementation for demo)
    """
    return {
        "status": "success",
        "city": city,
        "time": "10:30 AM"
    }


def mock_get_weather_forecast(city: str, date: str) -> Dict[str, float]:
    """Mock weather forecast service.
    Replace this with a real weather API call in production.
    Returns forecasted temperature in Celsius and precipitation in mm.
    """
    # For demo we hardcode a few cases:
    demo_db = {
        ("Amsterdam", "2025-10-28"): {"temp_c": 27.0, "rain_mm": 0.2},
        ("Amsterdam", "2025-10-29"): {"temp_c": 12.0, "rain_mm": 4.0},
        ("London",    "2025-10-28"): {"temp_c": 9.0,  "rain_mm": 5.5},
        ("Barcelona", "2025-10-28"): {"temp_c": 30.0, "rain_mm": 0.0},
    }
    return demo_db.get((city, date), {"temp_c": 20.0, "rain_mm": 0.0})


def get_weather_and_recommend(city: str, date: str) -> dict:
    """
    Tool callable by the agent.
    1. Get forecast (mock).
    2. Classify temp/rain.
    3. Suggest activities.
    4. Return machine-readable summary the LLM can explain to the user.
    """
    forecast = mock_get_weather_forecast(city, date)
    rec = recommend_activities(
        temp_c=forecast["temp_c"],
        rain_mm=forecast["rain_mm"]
    )

    return {
        "status": "success",
        "city": city,
        "date": date,
        "weather_forecast": {
            "temp_c": forecast["temp_c"],
            "rain_mm": forecast["rain_mm"],
            "temp_category": rec["temp_category"],
            "rain_category": rec["rain_category"],
        },
        "suggested_activities": rec["activities"],
        "explanation": rec["rationale"]
    }

# Quick smoke test
print(get_weather_and_recommend("Amsterdam", "2025-10-28"))
print(get_weather_and_recommend("London", "2025-10-28"))

# %% [markdown]
# ## 3. Define the Decision Agent
# 
# Now we create an Agent that:
# - understands it's an "Event Decision Agent"
# - knows it can call 2 tools:
#   - get_current_time
#   - get_weather_and_recommend
# - and is instructed to:
#   - recommend what kind of event to plan,
#   - justify the recommendation in business terms,
#   - mention risk (e.g. “high rain risk, move indoor to reduce cancellation cost”)
#
# This is now aligned with the hackathon topic: **Business Automation**.
# It's no longer just weather. It's: use weather to drive an event ops decision.

# %%
decision_agent = Agent(
    model="gemini-2.5-flash",
    name="decision_agent",
    description=(
        "Event Decision Agent that makes business recommendations about "
        "what type of event should be organized based on forecast weather, "
        "and explains operational risk."
    ),
    instruction=(
        "You are an Event Decision Agent for corporate event planning.\n"
        "- When the user asks about planning an event in a given city and date, "
        "call the 'get_weather_and_recommend' tool to retrieve forecasted "
        "temperature and precipitation, plus suitable activity types.\n"
        "- Use that to recommend:\n"
        "  * outdoor, indoor, or online format\n"
        "  * example activity types (e.g. team building, workshop, webinar)\n"
        "  * risk justification (rain risk, comfort, attendance impact)\n"
        "- If the user only wants current time in a city, you may call 'get_current_time'.\n"
        "- Always answer in concise business English suitable for a manager.\n"
        "- If asked about payment or booking next steps, explicitly say you can trigger a payment request "
        "after the event type is confirmed."
    ),
    tools=[get_current_time, get_weather_and_recommend],
)

# %% [markdown]
# ## 4. Example usage flow (pseudo-chat)
# 
# Below are example prompts you would send to the agent at runtime.
# (Exact API for calling `Agent` will depend on google.adk runtime, so we mock it here.)
#
# We simulate:
# - Ask: "We want to plan a customer meetup in Amsterdam on 2025-10-28. What format do you recommend?"
# - Agent SHOULD call `get_weather_and_recommend("Amsterdam","2025-10-28")`
# - Then respond with a recommendation.

# %%
# Pseudo code / illustration. Adjust to match your Agent runtime's .run() or .invoke() method.
def simulate_agent_call(city: str, date: str):
    tool_result = get_weather_and_recommend(city, date)

    # What the LLM would *see* from the tool:
    print("=== TOOL RESULT (what the agent tool would return) ===")
    print(tool_result)

    # And this is roughly what we'd expect the LLM to answer to end user:
    summary = (
        f"For {city} on {date}, forecast temperature is "
        f"{tool_result['weather_forecast']['temp_c']}°C "
        f"({tool_result['weather_forecast']['temp_category']}) "
        f"with expected precipitation {tool_result['weather_forecast']['rain_mm']} mm "
        f"({tool_result['weather_forecast']['rain_category']}).\n\n"
        f"Recommended event format: {tool_result['suggested_activities'][0]} or similar.\n"
        f"Rationale: {tool_result['explanation']}\n\n"
        "Operational note: Based on these conditions, we can proceed with booking and "
        "issuing the payment request for the venue/vendors."
    )

    print("\n=== EXPECTED AGENT SUMMARY TO USER ===")
    print(summary)

simulate_agent_call("Amsterdam", "2025-10-28")
simulate_agent_call("London", "2025-10-28")

# %% [markdown]
# ## 5. Next steps / how to present this at hackathon
# 
# - You can show the mapping table as your internal policy / business rule engine.
# - You can show `decision_agent` as the AI layer that automates:
#     - risk assessment,
#     - event type decision,
#     - and readiness to trigger payment.
# - Your teammate's payment trigger endpoint becomes the "next step after approval".
# 
# This tells a complete story:
# > data ingestion (weather) → decision policy (mapping) → agent reasoning (LLM) → business action (payment).
#
# Which matches "Automation for Business".
