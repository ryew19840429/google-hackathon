from google.adk.agents.llm_agent import Agent
from google.adk.tools.agent_tool import AgentTool
import requests
from google.adk.tools import google_search
from google import genai
from PIL import Image
from io import BytesIO
import json
from retreat_manager.utils.api_client import TikkieAPIClient

client = genai.Client(api_key="AIzaSyDT1Zq7M1yc3br4mTMAxh4F6EBtWFWymWs")

tikkie_client = TikkieAPIClient()

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
                image.save("marketing-image.png")
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
    description="A resort manager agent that checks the weather forecast for a specified city and recommends suitable events for 50 persons based on the weather conditions.",
    instruction="""
    1.You are a resort manager. Your primary goal is to check the weather forecast for a given city using the 'get_weather_forecast' tool and then recommend appropriate events for 50 guests based on the predicted weather. 
    2.Use the Google Search tool to find local attractions, specific event ideas, or popular activities for large groups in the specified city to enhance your recommendations.
    3.ALWAYS DO THIS!! With the recommendations, call generate_image tool to generate a nice advertising image that can be posted on social media. Also include text about some of the events. Make the design so great that you can win advertising awards for how engaging the image is.
    4.ALWAYS DO THIS!! After creating the image, tell the user where's the location of the file
    5.ALWAYS DO THIS!! Create one single tikkie for 125 euroes. Infer the description from the recommendation events, city and weather.
    6.If the user ask for an image, call the generate_image tool
    """,
    # ADDED the new generate_image tool to the list
    tools=[get_weather_forecast, AgentTool(agent=Agent_Search), generate_image, create_tikkie_request],
)

# You can now invoke the agent. For example:
# response = root_agent.generate_content("What's the weather in London tomorrow and suggest an event? Also, generate an image of a sunny park.")
# print(response)