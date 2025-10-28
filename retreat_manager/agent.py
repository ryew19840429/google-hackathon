from google.adk.agents.llm_agent import Agent
from google.adk.tools.agent_tool import AgentTool
import requests
from google.adk.tools import google_search
from google import genai
from PIL import Image
from io import BytesIO
import json
from dotenv import load_dotenv
import os

load_dotenv()

GOOGLE_API_KEY=os.getenv('GOOGLE_API_KEY')

client = genai.Client(api_key=GOOGLE_API_KEY)

# --- Image Generation Tool ---
def generate_image(prompt: str) -> dict:
    """Generates an image based on a text prompt and saves it as 'marketing-image.png'."""
    try:
        # Call the API to generate content
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=prompt,
        )

        image_saved = False
        text_response = ""
        
        # The response can contain both text and image data.
        # Iterate through the parts to find and save the image.
        if not response.candidates:
             return {"status": "error", "message": "No candidates found in response."}
             
        for part in response.candidates[0].content.parts:
            if part.text is not None:
                text_response += part.text + "\n"
            elif part.inline_data is not None:
                image = Image.open(BytesIO(part.inline_data.data))
                image.save("chat_ui/assets/marketing-image.png")
                image_saved = True

        if image_saved:
            return {"status": "success", "message": "Image saved as 'marketing-image.png'.", "text_response": text_response.strip()}
        elif text_response:
             return {"status": "info", "message": "No image generated, received text response.", "text_response": text_response.strip()}
        else:
             return {"status": "error", "message": "No image data or text found in response."}

    except Exception as e:
        return {"status": "error", "message": f"An error occurred: {str(e)}"}

# --- Weather Tool implementation ---
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

def create_tikkie_request(amount: float, description: str, **kwargs) -> str:
    """
    Creates a Tikkie payment request using the specified amount and description. Always return the full details of the created Tikkie.
    """
    
    # FIX: Move the import and instantiation inside the function call
    from retreat_manager.utils.api_client import TikkieAPIClient
    tikkie_client = TikkieAPIClient()
    
    if not amount or not description:
        return "Error: Could not obtain a valid amount or description to create the Tikkie request."

    data = {
        "amountInCents": int(amount * 100),
        "description": description[:35], # API limit: <= 35 characters
        "expiryDate": "2025-12-31" 
    }

    try:
        response_data = tikkie_client.post("paymentrequests", data)
        payment_request_url = response_data.get("paymentRequestUrl")
        
        if payment_request_url:
            return f"Tikkie request created: {payment_request_url}"
        else:
            return f"Error creating Tikkie request. API Response: {response_data}"
                
    except Exception as e:
        return f"An error occurred while creating Tikkie request: {e}"

# --- Agent Definitions ---

Agent_Search = Agent(
    model='gemini-2.0-flash-exp',
    name='SearchAgent',
    instruction="""
    You're a spealist in Google Search
    """,
    tools=[google_search]
)

root_agent = Agent(
    model="gemini-2.5-flash",
    name="resort_manager_agent",
    description="""
        This agent serves as a proactive Resort Manager focused on delivering a seamless and weather-appropriate guest experience. Its primary function is to optimize event planning for large groups (specifically 50 guests) in any user-specified city.

        Core Objectives:
        Weather-Informed Planning: Utilize the get_weather_forecast tool to determine the current or predicted weather conditions for the target city (e.g., Sunny, Rainy, Cold).

        Locally Sourced Recommendations: Employ the Google Search tool to find relevant, unique, and high-quality local attractions and activities specifically suitable for a group of 50.

        Complete Marketing Package Generation: Generate an award-worthy social media advertisement image using the generate_image tool, including key event highlights, to immediately promote the planned activities.

        Financial Administration: Automatically generate a Tikkie payment request (€125.00) for event contributions.

        Full-Service Summary: Provide a single, comprehensive output detailing the weather, the full event recommendations, the generated advertising image, and the Tikkie request.

        Mandatory Execution Flow:
        Check Weather Forecast.

        Perform Google Search for 50-person activities.

        Generate 3+ Themed Recommendations.

        Call generate_image for the Social Media Ad.

        State the Image File Location.

        Create the €125.00 Tikkie.

        Display the Full Summary (Recommendations, Image, and Tikkie).
    """,
    instruction="""
        Scenario: Resort Manager Event Planning

        Role: Resort Manager

        Primary Goal: Plan weather-appropriate events for 50 resort guests in a specified city, create a compelling social media advertisement, and handle the associated payment.

        Inputs Required from User:

        City: The city for which the event planning is required (e.g., "Miami, Florida" or "Kyoto, Japan").

        Execution Steps (MUST be performed in order):

        Weather Check & Event Planning:

        Tool: get_weather_forecast (Internal simulation/placeholder: assume this tool provides a simple condition like 'Sunny', 'Rainy', 'Cloudy', 'Snowy' and a temperature range).

        Action: Check the weather forecast for the user-specified city.

        Output: Determine a primary event theme/type (Indoor/Outdoor) based on the forecast.

        Local Research & Recommendation Enhancement:

        Tool: google:search

        Action: Use Google Search to find local attractions, specific event ideas, or popular activities suitable for a large group of 50 guests in the specified city, aligning with the weather condition.

        Output: Generate a detailed list of at least three (3) distinct event recommendations for the 50 guests (e.g., 'Guided Art Deco Walking Tour,' 'Private Beach BBQ,' 'Indoor Cooking Class').

        Advertising Image Generation (MANDATORY):

        Tool: generate_image

        Action: Call the generate_image tool to create a high-quality, engaging advertising image suitable for social media.

        Design Requirements: The image must look professional, award-winning, and feature text that mentions the city, the resort's hospitality, and highlight at least two of the recommended events (e.g., "Escape to [City]! Private Tours & Gourmet Dining Awaits!").

        Output: The generated image file.

        Image Location Confirmation (MANDATORY):

        Action: Immediately after image generation, state the file path or location where the generated image is stored.

        Tikkie Generation (MANDATORY):

        Action: Create a single Tikkie (payment request) for a fixed amount of €125.00.

        Description: The Tikkie description must be inferred naturally from the recommended events, the city, and the weather (e.g., "Contribution for [Event Type] in [City] due to [Weather] forecast").

        Output: The generated Tikkie link/summary.

        Final Summary Presentation (MANDATORY):

        Action: Display a complete, cohesive summary that includes ALL the generated elements.

        Summary Components (Must be in this order):

        Full recommendation summary (city, weather, and the list of 3+ events).

        The generated advertising image.

        The generated Tikkie link/summary.
    """,
    # ADDED the new generate_image tool to the list
    tools=[get_weather_forecast, AgentTool(agent=Agent_Search), generate_image, create_tikkie_request],
)