import os
import httpx

class TikkieAPIClient:
    def __init__(self):
        self.api_key = os.getenv("TIKKIE_API_KEY", "Nc7qAXW5xYD9GBhyAr3hlxsVl679LvyU")
        self.app_token = os.getenv("TIKKIE_APP_TOKEN", "9b765be7-e8a7-4726-8555-d03fe44f8664")
        self.base_url = "https://api-sandbox.abnamro.com/v2/tikkie"

        if not self.api_key or not self.app_token:
            raise ValueError("Tikkie API credentials not found in environment variables.")

        self.headers = {
            "API-Key": self.api_key,
            "X-App-Token": self.app_token,
            "Content-Type": "application/json",
        }

    def _send_request(self, method: str, endpoint: str, **kwargs):
        url = f"{self.base_url}/{endpoint}"
        try:
            with httpx.Client() as client:
                response = client.request(method, url, headers=self.headers, **kwargs)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            raise Exception(f"Error from Tikkie API ({e.response.status_code}): {e.response.text}") from e
        except Exception as e:
            raise Exception(f"An unexpected network error occurred: {e}") from e

    def post(self, endpoint: str, data: dict):
        return self._send_request("POST", endpoint, json=data)

    def get(self, endpoint: str, params: dict = None):
        return self._send_request("GET", endpoint, params=params)
