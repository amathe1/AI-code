# """
# Weather MCP Server using SerpAPI
# pip install mcp httpx python-dotenv
# Add to .env: SERPAPI_KEY=your_key_here
# Get free key: https://serpapi.com/manage-api-key
# Run: mcp dev weather_mcp_server.py
# """
# from dotenv import load_dotenv
# load_dotenv()

# import os
# import httpx
# from dotenv import load_dotenv
# from mcp.server.fastmcp import FastMCP

# load_dotenv()

# SERPAPI_KEY = os.getenv("SERPAPI_API_KEY")
# SERPAPI_URL = "https://serpapi.com/search.json"

# mcp = FastMCP("Weather Server")


# @mcp.tool()
# def get_weather(city: str) -> dict:
#     """
#     Get current weather for any city using SerpAPI.

#     Args:
#         city: City name e.g. 'Hyderabad', 'London', 'New York'

#     Returns:
#         Dict with temperature, humidity, wind, condition and 7-day forecast
#     """
#     # Call SerpAPI — searches Google for "weather in {city}"
#     response = httpx.get(SERPAPI_URL, params={
#         "q":       f"weather in {city}",
#         "engine":  "google",
#         "api_key": SERPAPI_KEY,
#         "hl":      "en",
#     })
#     response.raise_for_status()
#     data = response.json()

#     # SerpAPI puts weather inside answer_box
#     box = data.get("answer_box", {})

#     if not box or box.get("type") != "weather_result":
#         return {"error": f"No weather data found for '{city}'"}

#     # Extract 7-day forecast
#     forecast = [
#         {
#             "day":       day.get("day"),
#             "condition": day.get("weather"),
#             "high":      str(day.get("temperature", {}).get("high", "")) + "°F",
#             "low":       str(day.get("temperature", {}).get("low",  "")) + "°F",
#             "humidity":  day.get("humidity"),
#             "wind":      day.get("wind"),
#         }
#         for day in box.get("forecast", [])
#     ]

#     return {
#         "location":      box.get("location", city),
#         "date":          box.get("date"),
#         "condition":     box.get("weather"),
#         "temperature":   str(box.get("temperature", "")) + "°" + box.get("unit", "Fahrenheit")[0],
#         "humidity":      box.get("humidity"),
#         "wind":          box.get("wind"),
#         "precipitation": box.get("precipitation"),
#         "forecast":      forecast,
#     }


# @mcp.tool()
# def compare_weather(city1: str, city2: str) -> dict:
#     """
#     Compare current weather between two cities.

#     Args:
#         city1: First city  e.g. 'Hyderabad'
#         city2: Second city e.g. 'Mumbai'

#     Returns:
#         Side-by-side comparison with warmer city identified
#     """
#     w1 = get_weather(city1)
#     w2 = get_weather(city2)

#     return {
#         city1:    w1,
#         city2:    w2,
#         "warmer": city1 if w1["temperature"] > w2["temperature"] else city2,
#     }


# if __name__ == "__main__":
#     print(f"SERPAPI_KEY : {'SET ✅' if SERPAPI_KEY else 'NOT SET ❌'}")
#     mcp.run()

"""
Weather MCP Server using SerpAPI
pip install mcp httpx python-dotenv
"""

import os
import sys
import httpx
from pathlib import Path
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# ── Load .env from same folder as this file ───────────────
load_dotenv(Path(__file__).parent / ".env")

SERPAPI_KEY = os.getenv("SERPAPI_API_KEY", "")
SERPAPI_URL = "https://serpapi.com/search.json"

# ── CRITICAL: use stderr NOT stdout ───────────────────────
# stdout is used by MCP protocol — any print() to stdout
# corrupts the stdio pipe and causes "Connection closed"
def log(msg):
    print(msg, file=sys.stderr, flush=True)

log(f"SERPAPI_KEY : {'SET' if SERPAPI_KEY else 'NOT SET'}")

mcp = FastMCP("Weather Server")


@mcp.tool()
def get_weather(city: str) -> dict:
    """
    Get current weather for any city using SerpAPI.

    Args:
        city: City name e.g. 'Hyderabad', 'London', 'New York'

    Returns:
        Dict with temperature, humidity, wind, condition and 7-day forecast
    """
    log(f"Fetching weather for: {city}")

    response = httpx.get(SERPAPI_URL, params={
        "q":       f"weather in {city}",
        "engine":  "google",
        "api_key": SERPAPI_KEY,
        "hl":      "en",
    })
    response.raise_for_status()
    data = response.json()

    box = data.get("answer_box", {})

    if not box or box.get("type") != "weather_result":
        return {"error": f"No weather data found for '{city}'"}

    forecast = [
        {
            "day":       day.get("day"),
            "condition": day.get("weather"),
            "high":      str(day.get("temperature", {}).get("high", "")) + "°F",
            "low":       str(day.get("temperature", {}).get("low",  "")) + "°F",
            "humidity":  day.get("humidity"),
            "wind":      day.get("wind"),
        }
        for day in box.get("forecast", [])
    ]

    result = {
        "location":      box.get("location", city),
        "date":          box.get("date"),
        "condition":     box.get("weather"),
        "temperature":   str(box.get("temperature", "")) + "°" + box.get("unit", "Fahrenheit")[0],
        "humidity":      box.get("humidity"),
        "wind":          box.get("wind"),
        "precipitation": box.get("precipitation"),
        "forecast":      forecast,
    }

    log(f"Weather fetched: {result['location']} - {result['temperature']}")
    return result


@mcp.tool()
def compare_weather(city1: str, city2: str) -> dict:
    """
    Compare current weather between two cities.

    Args:
        city1: First city  e.g. 'Hyderabad'
        city2: Second city e.g. 'Mumbai'

    Returns:
        Side-by-side comparison with warmer city identified
    """
    w1 = get_weather(city1)
    w2 = get_weather(city2)

    return {
        city1:    w1,
        city2:    w2,
        "warmer": city1 if w1.get("temperature","") > w2.get("temperature","") else city2,
    }


if __name__ == "__main__":
    log("Starting Weather MCP Server...")
    mcp.run(transport="stdio")   # ← explicit stdio transport