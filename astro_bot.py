"""AstroBot - Webex bot for weather, ISS position, and stargazing data."""
import os
import time
from datetime import datetime, timezone
from typing import Any

import requests
from dotenv import load_dotenv

WEBEX = "https://webexapis.com/v1"
OPENWEATHER = "https://api.openweathermap.org"
ISS_URL = "http://api.open-notify.org/iss-now.json"
OPEN_METEO = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = 15


class ApiError(Exception):
    """Raised when an external API cannot provide usable data."""


def required_setting(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing {name}. Add it to your .env file.")
    return value


def request_json(method: str, url: str, **kwargs: Any) -> dict[str, Any] | list[Any]:
    """Make an HTTP request and turn network, status, and JSON errors into one safe error."""
    try:
        response = requests.request(method, url, timeout=TIMEOUT, **kwargs)
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "60")
            raise ApiError(f"Rate limited by the service. Retrying after {retry_after} seconds.")
        response.raise_for_status()
        return response.json()
    except requests.Timeout as exc:
        raise ApiError("The service timed out. Please try again shortly.") from exc
    except requests.RequestException as exc:
        raise ApiError(f"The service request failed: {exc}") from exc
    except ValueError as exc:
        raise ApiError("The service returned invalid JSON.") from exc


def webex_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def get_rooms(token: str) -> list[dict[str, Any]]:
    data = request_json("GET", f"{WEBEX}/rooms", headers=webex_headers(token))
    return data.get("items", []) if isinstance(data, dict) else []


def choose_room(rooms: list[dict[str, Any]]) -> dict[str, Any]:
    if not rooms:
        raise ApiError("No Webex rooms were returned. Check the bot token and room membership.")
    print("\nAvailable Webex rooms:")
    for index, room in enumerate(rooms, start=1):
        print(f"{index}. {room.get('title', 'Untitled')} ({room.get('type', 'unknown')})")
    while True:
        selection = input("Choose a room number: ").strip()
        if selection.isdigit() and 1 <= int(selection) <= len(rooms):
            return rooms[int(selection) - 1]
        print("Please enter a valid room number.")


def latest_message(token: str, room_id: str) -> dict[str, Any] | None:
    # Webex bots can read group-space messages only when they are mentioned.
    data = request_json(
        "GET",
        f"{WEBEX}/messages",
        headers=webex_headers(token),
        params={"roomId": room_id, "max": 1, "mentionedPeople": "me"},
    )
    items = data.get("items", []) if isinstance(data, dict) else []
    return items[0] if items else None


def send_message(token: str, room_id: str, text: str) -> None:
    request_json("POST", f"{WEBEX}/messages", headers=webex_headers(token), json={"roomId": room_id, "text": text})


def epoch_to_utc(timestamp: int | float | str | None) -> str:
    try:
        return datetime.fromtimestamp(float(timestamp), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    except (TypeError, ValueError, OverflowError, OSError):
        return "Unknown time"


def geocode_city(city: str, api_key: str) -> dict[str, Any]:
    data = request_json("GET", f"{OPENWEATHER}/geo/1.0/direct", params={"q": city, "limit": 1, "appid": api_key})
    if not isinstance(data, list) or not data:
        raise ApiError(f"I could not find a location called '{city}'.")
    return data[0]


def reverse_geocode(lat: str | float, lon: str | float, api_key: str) -> str:
    data = request_json("GET", f"{OPENWEATHER}/geo/1.0/reverse", params={"lat": lat, "lon": lon, "limit": 1, "appid": api_key})
    if isinstance(data, list) and data:
        place = data[0]
        return ", ".join(part for part in [place.get("name"), place.get("state"), place.get("country")] if part)
    return "Unknown location"


def get_weather(lat: str | float, lon: str | float, api_key: str) -> dict[str, Any]:
    data = request_json("GET", f"{OPENWEATHER}/data/2.5/weather", params={"lat": lat, "lon": lon, "appid": api_key, "units": "metric"})
    if not isinstance(data, dict):
        raise ApiError("Weather API returned an unexpected response.")
    return data


def stargazing_advice(weather: dict[str, Any]) -> str:
    clouds = weather.get("clouds", {}).get("all", 100)
    description = weather.get("weather", [{}])[0].get("main", "Unknown").lower()
    if clouds <= 30 and description not in {"rain", "snow", "thunderstorm"}:
        return "Good potential for stargazing: low cloud cover."
    if clouds <= 60:
        return "Fair potential for stargazing: some cloud cover expected."
    return "Poor potential for stargazing: high cloud cover or unsuitable conditions."


def format_weather(place: str, weather: dict[str, Any]) -> str:
    main = weather.get("main", {})
    condition = weather.get("weather", [{}])[0].get("description", "Unknown")
    clouds = weather.get("clouds", {}).get("all", "N/A")
    visibility = weather.get("visibility", "N/A")
    visibility_text = f"{visibility / 1000:.1f} km" if isinstance(visibility, (int, float)) else "N/A"
    return (f"Weather for {place}\n"
            f"Condition: {condition.title()}\n"
            f"Temperature: {main.get('temp', 'N/A')} °C\n"
            f"Cloud cover: {clouds}%\nVisibility: {visibility_text}\n"
            f"{stargazing_advice(weather)}")


def handle_weather(argument: str, weather_key: str) -> str:
    if not argument:
        return "Usage: /weather city name  (example: /weather Hatfield)"
    location = geocode_city(argument, weather_key)
    weather = get_weather(location["lat"], location["lon"], weather_key)
    place = ", ".join(part for part in [location.get("name"), location.get("state"), location.get("country")] if part)
    return format_weather(place, weather)


def handle_iss(weather_key: str) -> str:
    data = request_json("GET", ISS_URL)
    if not isinstance(data, dict) or data.get("message") != "success":
        raise ApiError("ISS service did not return a successful position.")
    position = data.get("iss_position", {})
    lat, lon = position.get("latitude"), position.get("longitude")
    if lat is None or lon is None:
        raise ApiError("ISS service response did not include coordinates.")
    place = reverse_geocode(lat, lon, weather_key)
    weather = get_weather(lat, lon, weather_key)
    return (f"ISS location\nTime: {epoch_to_utc(data.get('timestamp'))}\n"
            f"Coordinates: {lat}, {lon}\nNearest location: {place}\n\n{format_weather(place, weather)}")


def handle_sky(argument: str, weather_key: str) -> str:
    """Extension feature: sunrise, sunset and moon data for observation planning."""
    if not argument:
        return "Usage: /sky city name  (example: /sky Hatfield)"
    location = geocode_city(argument, weather_key)
    data = request_json(
        "GET", OPEN_METEO,
        params={
            "latitude": location["lat"], "longitude": location["lon"],
            "daily": "sunrise,sunset,moonrise,moonset,moon_phase",
            "timezone": "auto", "forecast_days": 1,
        },
    )
    if not isinstance(data, dict):
        raise ApiError("Astronomy service returned an unexpected response.")
    daily = data.get("daily", {})
    value = lambda field: daily.get(field, ["N/A"])[0]
    place = ", ".join(part for part in [location.get("name"), location.get("country")] if part)
    return (f"Sky guide for {place}\nSunrise: {value('sunrise')}\nSunset: {value('sunset')}\n"
            f"Moonrise: {value('moonrise')}\nMoonset: {value('moonset')}\n"
            f"Moon phase value: {value('moon_phase')}\nUse this with /weather to plan observing.")


def process_command(text: str, weather_key: str) -> str | None:
    command, _, argument = text.strip().partition(" ")
    command = command.lower()
    if command == "/weather":
        return handle_weather(argument.strip(), weather_key)
    if command == "/iss":
        return handle_iss(weather_key)
    if command == "/sky":
        return handle_sky(argument.strip(), weather_key)
    if command == "/help":
        return "Commands: /weather city name, /iss, /sky city name"
    return "Unknown command. Use /help."


def monitor_room(token: str, bot_email: str, room_id: str, weather_key: str) -> None:
    processed_ids: set[str] = set()
    poll_seconds = max(5, int(os.getenv("POLL_SECONDS", "5")))
    print("Monitoring room. Press Ctrl+C to stop.")
    while True:
        try:
            message = latest_message(token, room_id)
            if message:
                message_id = message.get("id", "")
                text = (message.get("text") or "").strip()
                is_own_message = message.get("personEmail", "").lower() == bot_email.lower()
                if message_id and message_id not in processed_ids and not is_own_message:
                    processed_ids.add(message_id)
                    # In a group space Webex requires users to @mention the bot;
                    # accept the command portion after that mention.
                    command_start = text.find("/")
                    if command_start >= 0:
                        try:
                            answer = process_command(text[command_start:], weather_key)
                            if answer:
                                send_message(token, room_id, answer)
                        except ApiError as exc:
                            send_message(token, room_id, f"Sorry, I could not complete that request: {exc}")
            time.sleep(poll_seconds)
        except ApiError as exc:
            print(f"Polling error: {exc}")
            # Avoid repeated calls while an API has temporarily rate-limited us.
            time.sleep(60 if "Rate limited" in str(exc) else poll_seconds)


def main() -> None:
    load_dotenv()
    token = required_setting("WEBEX_ACCESS_TOKEN")
    bot_email = required_setting("WEBEX_BOT_EMAIL")
    weather_key = required_setting("OPENWEATHER_API_KEY")
    room = choose_room(get_rooms(token))
    monitor_room(token, bot_email, room["id"], weather_key)


if __name__ == "__main__":
    main()
