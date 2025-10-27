# %% [markdown]
# # Event Decision Agent (with Weather Policy Rules)
#
# This notebook builds an AI Agent that:
# - Looks at forecast weather (temperature, rain, wind, cloud cover)
# - Classifies those conditions into business-friendly categories
# - Chooses recommended activity types (outdoor / indoor / remote)
# - Explains the reasoning so a manager can approve budget & trigger payment
#
# This version includes:
# - temperature category
# - rain category
# - wind category
# - and basic sun/cloud cover, which can be exposed in reasoning


# %%
from typing import Dict, List
from google.adk.agents.llm_agent import Agent


# %% [markdown]
# ## 1. Weather → Activity Mapping
# We define a policy table ("literature-based") that encodes best-practice guidelines:
# - temp: Hot / Mild / Cold
# - rain: Dry / Rainy
# - wind: Calm / Windy
#
# The agent will NOT hallucinate this logic. It will call a tool
# that returns a deterministic recommendation based on this table.
#
# NOTE:
# - "Rainy" is defined as precipitation_mm_per_hr >= 0.1
# - "Windy" is defined as wind_speed_m_per_s > 8.0
# - We'll consider "Calm" otherwise for wind
# - We'll still capture sun/cloud for explanation, but mapping currently keys on temp/rain/wind.

# %%
weather_mapping = [
    # ☀️ Sunny & Dry (but "sunny" itself is not in the key, it's used for explanation later)
    {"temp": "Hot",  "rain": "Dry",   "wind": "Calm",
     "activities": ["Swimming", "Outdoor music festivals", "BBQ"],
     "rationale":  "Hot, dry, low wind → outdoor gathering is comfortable and stable."},

    {"temp": "Hot",  "rain": "Dry",   "wind": "Windy",
     "activities": ["Beach walking", "Windsurfing", "Outdoor cafés"],
     "rationale":  "Hot, dry but windy → wind sports and short outdoor hangs are okay; avoid tents/stages."},

    {"temp": "Mild", "rain": "Dry",   "wind": "Calm",
     "activities": ["Hiking", "Cycling", "Open markets"],
     "rationale":  "Mild temp, dry, calm → ideal for casual outdoor and light physical activity."},

    {"temp": "Mild", "rain": "Dry",   "wind": "Windy",
     "activities": ["Park strolls", "Photography", "Outdoor jogging"],
     "rationale":  "Mild and windy → okay for short-duration outdoor movement, but less ideal for long static setups."},

    {"temp": "Cold", "rain": "Dry",   "wind": "Calm",
     "activities": ["Museum visits", "City walks", "Warm cafés"],
     "rationale":  "Cold but calm and dry → short outdoor walks plus mostly indoor cultural / warm stops."},

    {"temp": "Cold", "rain": "Dry",   "wind": "Windy",
     "activities": ["Indoor gyms", "Board games", "Libraries"],
     "rationale":  "Cold + dry + windy → outdoor comfort is low; keep participants indoors."},

    # 🌧 Rainy Conditions
    {"temp": "Hot",  "rain": "Rainy", "wind": "Calm",
     "activities": ["Indoor exhibitions", "Cinema", "Café meetups"],
     "rationale":  "Warm but rainy → people are willing to travel, but prefer covered/indoor social activities."},

    {"temp": "Hot",  "rain": "Rainy", "wind": "Windy",
     "activities": ["Shopping malls", "Indoor sports", "Cooking at home"],
     "rationale":  "Warm, rainy, and windy → outdoor travel gets annoying; move to indoor leisure."},

    {"temp": "Mild", "rain": "Rainy", "wind": "Calm",
     "activities": ["Art galleries", "Workshops", "Indoor reading"],
     "rationale":  "Mild temp + rain → cozy, culturally oriented indoor activities work well."},

    {"temp": "Mild", "rain": "Rainy", "wind": "Windy",
     "activities": ["Indoor sports", "Board games", "Work from café"],
     "rationale":  "Mild temp but rainy and windy → limit movement, keep people in one sheltered location."},

    {"temp": "Cold", "rain": "Rainy", "wind": "Calm",
     "activities": ["Home cooking", "Cinemas", "Indoor concerts"],
     "rationale":  "Cold + rain → going outside is unpleasant; entertainment should be indoors and warm."},

    {"temp": "Cold", "rain": "Rainy", "wind": "Windy",
     "activities": ["Stay home", "Indoor movie", "Online gaming"],
     "rationale":  "Cold, rainy, and windy → high dropout risk. Recommend remote/online or home-based plans."},
]


# %% [markdown]
# ## 2. Classifiers
# We categorize raw weather numbers into the discrete buckets used in `weather_mapping`.
#
# Assumptions / thresholds:
# - Temperature in °C:
#       Hot  : > 25
#       Mild : > 10 and ≤ 25
#       Cold : ≤ 10
#
# - Rainy vs Dry:
#       Rainy if precipitation_mm_per_hr >= 0.1
#       Dry otherwise
#
# - Wind:
#       Windy if wind_speed_m_per_s > 8.0
#       Calm otherwise
#
# - Sunny / Cloudy (not used as a key, but nice for explanation in text output):
#       Sunny if cloud_cover_percent < 30
#       Cloudy otherwise

# %%
def classify_temp(temp_c: float) -> str:
    """Return 'Hot', 'Mild', or 'Cold' based on °C."""
    if temp_c > 25:
        return "Hot"
    elif temp_c > 10:
        return "Mild"
    else:
        return "Cold"


def classify_rain(precip_mm_per_hr: float) -> str:
    """Return 'Rainy' or 'Dry' based on precipitation mm/hr."""
    if precip_mm_per_hr >= 0.1:
        return "Rainy"
    else:
        return "Dry"


def classify_wind(wind_speed_m_per_s: float) -> str:
    """Return 'Windy' or 'Calm' based on wind speed (m/s)."""
    if wind_speed_m_per_s > 8.0:
        return "Windy"
    else:
        return "Calm"


def classify_sky(cloud_cover_percent: float) -> str:
    """Return 'Sunny/Clear' or 'Cloudy/Overcast' for explanation."""
    if cloud_cover_percent < 30:
        return "Sunny/Clear"
    else:
        return "Cloudy/Overcast"


# %% [markdown]
# ## 3. Mapping Lookup
# Given (temp_cat, rain_cat, wind_cat), we pick the first matching rule from `weather_mapping`.
# We also include sky condition in the explanation for business context, but sky is not part of the key.

# %%
def lookup_weather_rule(temp_cat: str, rain_cat: str, wind_cat: str) -> Dict:
    """Find the first rule that matches temp/rain/wind categories."""
    for row in weather_mapping:
        if (
            row["temp"] == temp_cat and
            row["rain"] == rain_cat and
            row["wind"] == wind_cat
        ):
            return row
    # fallback if nothing matches
    return {
        "activities": [],
        "rationale": "No predefined rule for this combination."
    }


def recommend_activities(
    temp_c: float,
    precip_mm_per_hr: float,
    wind_speed_m_per_s: float,
    cloud_cover_percent: float
) -> Dict:
    """
    Build a structured recommendation object using:
    - classified categories
    - mapped activity suggestions
    - rationale for business explanation
    """
    tcat  = classify_temp(temp_c)
    rcat  = classify_rain(precip_mm_per_hr)
    wcat  = classify_wind(wind_speed_m_per_s)
    sky   = classify_sky(cloud_cover_percent)

    rule  = lookup_weather_rule(tcat, rcat, wcat)

    return {
        "categories": {
            "temp_category": tcat,
            "rain_category": rcat,
            "wind_category": wcat,
            "sky_condition": sky
        },
        "raw_weather": {
            "temperature_c": temp_c,
            "precip_mm_per_hr": precip_mm_per_hr,
            "wind_speed_m_per_s": wind_speed_m_per_s,
            "cloud_cover_percent": cloud_cover_percent
        },
        "suggested_activities": rule["activities"],
        "rationale": rule["rationale"]
    }


# quick smoke tests
print(recommend_activities(temp_c=30.0, precip_mm_per_hr=0.0, wind_speed_m_per_s=3.0, cloud_cover_percent=10))
print(recommend_activities(temp_c=12.0, precip_mm_per_hr=0.2, wind_speed_m_per_s=10.0, cloud_cover_percent=90))
print(recommend_activities(temp_c=5.0, precip_mm_per_hr=0.5, wind_speed_m_per_s=12.0, cloud_cover_percent=95))


# %% [markdown]
# ## 4. Mock Weather Tool
#
# We'll expose a tool the agent can call: `get_weather_and_recommend(city, date)`.
#
# For hackathon demo, we mock weather for a few cities/dates and return:
# - temperature (°C)
# - precipitation (mm/hr)
# - wind speed (m/s)
# - cloud cover (%)
#
# Then we run `recommend_activities(...)` using that mock forecast.
#
# IMPORTANT:
# The output of this tool is EXACTLY what the LLM agent will see, so we keep it structured.

# %%
def get_current_time(city: str) -> dict:
    """Returns the current time in a specified city. (Mock demo tool)"""
    return {
        "status": "success",
        "city": city,
        "time": "10:30 AM"
    }


def mock_get_weather_forecast(city: str, date: str) -> Dict[str, float]:
    """
    Mock forecast.
    In production, replace this with a real weather API (Open-Meteo, etc.).
    Units:
      temp_c → °C
      precip_mm_per_hr → mm/hr
      wind_speed_m_per_s → m/s
      cloud_cover_percent → %
    """
    demo_db = {
        ("Amsterdam", "2025-10-28"): {
            "temp_c": 27.0,
            "precip_mm_per_hr": 0.0,
            "wind_speed_m_per_s": 4.0,
            "cloud_cover_percent": 20.0
        },  # Hot, Dry, Calm, Sunny/Clear

        ("Amsterdam", "2025-10-29"): {
            "temp_c": 12.0,
            "precip_mm_per_hr": 0.3,
            "wind_speed_m_per_s": 10.0,
            "cloud_cover_percent": 95.0
        },  # Mild, Rainy, Windy, Cloudy/Overcast

        ("London", "2025-10-28"): {
            "temp_c": 9.0,
            "precip_mm_per_hr": 0.6,
            "wind_speed_m_per_s": 12.0,
            "cloud_cover_percent": 90.0
        },  # Cold, Rainy, Windy, Cloudy/Overcast

        ("Barcelona", "2025-10-28"): {
            "temp_c": 30.0,
            "precip_mm_per_hr": 0.0,
            "wind_speed_m_per_s": 9.0,
            "cloud_cover_percent": 15.0
        },  # Hot, Dry, Windy, Sunny/Clear
    }

    return demo_db.get(
        (city, date),
        {
            "temp_c": 20.0,
            "precip_mm_per_hr": 0.0,
            "wind_speed_m_per_s": 3.0,
            "cloud_cover_percent": 40.0
        }  # Default: Mild, Dry, Calm-ish / Cloudy
    )


def get_weather_and_recommend(city: str, date: str) -> dict:
    """
    Tool callable by the agent:
    1. Get forecast.
    2. Classify weather into categories (temp/rain/wind/sky).
    3. Match against weather_mapping.
    4. Return suggested activities and rationale.
    """
    forecast = mock_get_weather_forecast(city, date)

    rec = recommend_activities(
        temp_c=forecast["temp_c"],
        precip_mm_per_hr=forecast["precip_mm_per_hr"],
        wind_speed_m_per_s=forecast["wind_speed_m_per_s"],
        cloud_cover_percent=forecast["cloud_cover_percent"]
    )

    return {
        "status": "success",
        "city": city,
        "date": date,
        "categories": rec["categories"],       # Hot/Mild/Cold, Dry/Rainy, Calm/Windy, Sunny/Cloudy
        "raw_weather": rec["raw_weather"],     # numeric values
        "suggested_activities": rec["suggested_activities"],
        "business_rationale": rec["rationale"],
        "business_note": (
            "These suggestions are based on predefined safety/comfort rules. "
            "After you pick one activity format, I can proceed with vendor booking "
            "and trigger the payment request workflow."
        )
    }


# smoke check
print(get_weather_and_recommend("Amsterdam", "2025-10-28"))
print(get_weather_and_recommend("Amsterdam", "2025-10-29"))
print(get_weather_and_recommend("London", "2025-10-28"))
print(get_weather_and_recommend("Barcelona", "2025-10-28"))


# %% [markdown]
# ## 5. Define the AI Agent
#
# We now create an Agent that:
# - understands it's an "Event Decision Agent"
# - knows it has 2 tools:
#   - `get_weather_and_recommend` (the main one)
#   - `get_current_time` (still available; shows multi-tool orchestration)
#
# The instruction tells it how to act like a business automation agent:
# - recommend activity format
# - mention risk / comfort
# - explain why this supports budget approval
# - mention it can trigger payment after decision

# %%
decision_agent = Agent(
    model="gemini-2.5-flash",
    name="decision_agent",
    description=(
        "Event Decision Agent that recommends suitable activity formats "
        "based on forecast weather (temperature, rain, wind, sky) and "
        "explains operational risk for planning and vendor payment."
    ),
    instruction=(
        "You are an Event Decision Agent for corporate and customer events.\n"
        "\n"
        "When the user asks about planning an event in a given city and date:\n"
        "1. Call the 'get_weather_and_recommend' tool to retrieve:\n"
        "   - forecast temperature, rain, wind, and cloud cover\n"
        "   - categorized conditions (Hot/Mild/Cold, Dry/Rainy, Calm/Windy)\n"
        "   - suggested activity types and rationale\n"
        "2. Recommend:\n"
        "   - outdoor / indoor / remote format\n"
        "   - concrete examples of activities from the tool output\n"
        "   - logistics risk (e.g. high wind, rain, comfort)\n"
        "3. Explain briefly why this plan is low risk and budget-justified.\n"
        "4. End by saying you can proceed to vendor booking and trigger payment "
        "once the user confirms the format.\n"
        "\n"
        "If the user only wants the current time in a city, use 'get_current_time'.\n"
        "Always answer in concise business English for a manager.\n"
    ),
    tools=[get_current_time, get_weather_and_recommend],
)


# %% [markdown]
# ## 6. Example usage (simulation)
#
# We simulate how the agent would use the tool and then respond.
# In a real runtime, `decision_agent` would internally decide to call
# `get_weather_and_recommend`. Here we manually call that tool and show
# an example manager-facing message.

# %%
def simulate_manager_question(city: str, date: str):
    tool_result = get_weather_and_recommend(city, date)

    print("=== TOOL RESULT (what the tool returns to the agent) ===")
    print(tool_result)

    cats = tool_result["categories"]
    acts = tool_result["suggested_activities"]
    rationale = tool_result["business_rationale"]

    # This is roughly what we'd expect the LLM to reply to the end user:
    manager_summary = (
        f"For {city} on {date}, conditions are categorized as:\n"
        f"- Temp: {cats['temp_category']}\n"
        f"- Rain: {cats['rain_category']}\n"
        f"- Wind: {cats['wind_category']}\n"
        f"- Sky:  {cats['sky_condition']}\n\n"
        f"Recommended activity format: {acts[0] if acts else 'indoor/remote plan'}.\n"
        f"Alternative options: {', '.join(acts[1:]) if len(acts) > 1 else 'N/A'}.\n\n"
        f"Reasoning: {rationale}\n\n"
        "Operational note: Based on this, I can proceed with vendor booking "
        "and trigger the payment request workflow once you confirm the format."
    )

    print("\n=== EXPECTED AGENT SUMMARY TO MANAGER ===")
    print(manager_summary)


simulate_manager_question("Amsterdam", "2025-10-28")
simulate_manager_question("Amsterdam", "2025-10-29")
simulate_manager_question("London", "2025-10-28")
simulate_manager_question("Barcelona", "2025-10-28")


# %% [markdown]
# ## 7. Hackathon pitch takeaways
#
# - You now have:
#   - Deterministic rule base (governance-friendly, auditable).
#   - Tool-using LLM agent (Google ADK Agent).
#   - Clear business action hook (book vendor + trigger payment).
#
# - Judges love:
#   - Risk mitigation logic (windy/rainy -> move indoors).
#   - Automation narrative ("We take weather risk off the manager's plate").
#   - Cost control narrative ("We don't pay for outdoor staging in unsafe weather").
#
# This directly fits the "Automation for Business" track.
