# AstroBot API Investigation

## Project summary
AstroBot is a Python Webex bot for the Astronomy Club. It polls one selected Webex room every five seconds, ignores duplicate and bot messages, and responds to `/weather city`, `/iss`, `/sky city`, and `/help`. It uses JSON over HTTP and keeps API secrets in a local `.env` file.

## Run instructions
1. Create and activate a virtual environment.
2. Run `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and add your own Webex and OpenWeather keys.
4. Run `python astro_bot.py`, select the Webex room, then send commands from a different Webex account.

## API investigation
| API | Endpoint and HTTP method | Authentication | JSON used |
|---|---|---|---|
| Webex Rooms | `GET https://webexapis.com/v1/rooms` | `Authorization: Bearer <token>` | `items[]` contains room `id`, `title`, and `type`. |
| Webex Messages | `GET /v1/messages?roomId=<id>&max=1`; `POST /v1/messages` | Bearer token | GET returns `items[]`; POST body has `roomId` and `text`. |
| ISS | `GET http://api.open-notify.org/iss-now.json` | None | `timestamp`, `iss_position.latitude`, `iss_position.longitude`. |
| OpenWeather direct geocoding | `GET /geo/1.0/direct?q=<city>&limit=1&appid=<key>` | `appid` query parameter | Array with `name`, `lat`, `lon`, country and optional state. |
| OpenWeather reverse geocoding | `GET /geo/1.0/reverse?lat=<lat>&lon=<lon>&limit=1&appid=<key>` | `appid` query parameter | Array with readable location fields. |
| OpenWeather current weather | `GET /data/2.5/weather?lat=<lat>&lon=<lon>&units=metric&appid=<key>` | `appid` query parameter | `weather[0].description`, `main.temp`, `clouds.all`, `visibility`. |
| Open-Meteo astronomy extension | `GET https://api.open-meteo.com/v1/forecast` | No API key required | `daily.sunrise`, `daily.sunset`, `daily.moonrise`, `daily.moonset`, `daily.moon_phase`. |

Official documentation: [Webex Rooms](https://developer.webex.com/docs/api/v1/rooms), [Webex Messaging](https://developer.webex.com/messaging/docs/getting-started), [OpenWeather Current Weather](https://openweathermap.org/api/current), [OpenWeather Geocoding](https://openweathermap.org/api/geocoding-api), [Open Notify ISS](https://open-notify.org/Open-Notify-API/ISS-Location-Now/), and [NASA APOD](https://api.nasa.gov/).

## Epoch to human time
The ISS API timestamp is Unix/POSIX seconds. `datetime.fromtimestamp(timestamp, tz=timezone.utc)` converts it to a timezone-aware UTC date/time, then `strftime` formats it for the Webex message. Python recommends an aware UTC datetime rather than `utcfromtimestamp()`. [Python datetime documentation](https://docs.python.org/3/library/datetime.html)

## Web architecture
AstroBot is a client. Webex, OpenWeather, Open Notify and NASA expose server-side REST APIs. The Python client sends HTTP requests, the server returns JSON, and the bot parses only the fields needed for a user-friendly response. API keys/tokens prove authorisation; HTTPS protects the Webex, OpenWeather and NASA requests in transit.

## RESTful API concepts
`GET` reads resources without changing them: rooms, messages, ISS location and weather. `POST` creates a Webex message using a JSON body. Typical responses are `200 OK` for successful GET, `201 Created` for a new message, `400` for a bad request, `401` for missing/invalid credentials, `403` for insufficient permission, `404` for a missing resource, `429` for rate limiting, and `5xx` for server faults.

## MVC design pattern
The code is kept modular: API functions act as the model/data layer, `format_weather` and the command response strings form the view, and `process_command` plus `monitor_room` are the controller. This makes each concern easier to test and change.

## Security and reliability
- `.env` is ignored by Git; `.env.example` contains no real secrets.
- Never commit, record, or share access tokens.
- Requests use a timeout and errors are caught before a safe message is sent.
- Missing JSON fields use safe defaults such as `Unknown` or `N/A`.
- Commands are validated and duplicates/self-messages are ignored.
- The five-second polling interval respects the assignment guidance and the ISS API's recommended maximum polling rate.

## Test evidence to collect
Record screenshots/video evidence for: valid `/weather Hatfield`; invalid `/weather madeupplace`; `/iss`; `/sky Hatfield`; `/help`; invalid command; missing/invalid API key; and proof that repeating a poll does not repeat the same reply.

## Reflection
The most difficult integration issue was converting one service's output into another service's input: ISS coordinates go into reverse geocoding and then weather. Modular helper functions made errors easier to isolate. If developing further, I would add automated mocked tests and switch Webex polling to webhooks for a more efficient event-driven design.

## Completed template detail

### Webex Messaging API

| Criteria | Details |
|---|---|
| API Base URL | `https://webexapis.com/v1` |
| Authentication | Bearer access token in the `Authorization` header |
| List rooms | `GET /rooms` |
| Get latest room message | `GET /messages?roomId=<room_id>&max=1` |
| Send response | `POST /messages` with JSON `{ "roomId": "...", "text": "..." }` |
| Required headers | `Authorization: Bearer <token>`; POST also needs `Content-Type: application/json` |
| Example | `GET https://webexapis.com/v1/rooms` |

### ISS API sample JSON

```json
{
  "message": "success",
  "timestamp": 1710000000,
  "iss_position": {"latitude": "51.5", "longitude": "-0.1"}
}
```

### Geocoding sample JSON

OpenWeather is used. Its base URL is `https://api.openweathermap.org`; direct geocoding uses `/geo/1.0/direct`, reverse geocoding uses `/geo/1.0/reverse`, and authentication is the `appid` query parameter. A reverse request is `GET /geo/1.0/reverse?lat=51.5&lon=-0.1&limit=1&appid=<key>`.

```json
[{"name": "London", "lat": 51.5073, "lon": -0.1276, "country": "GB"}]
```

### Weather sample JSON

OpenWeather current weather uses `GET /data/2.5/weather?lat=<lat>&lon=<lon>&units=metric&appid=<key>`.

```json
{"weather": [{"description": "clear sky"}], "main": {"temp": 12.4, "humidity": 68}, "wind": {"speed": 2.6}, "clouds": {"all": 5}}
```

### Extended feature

Open-Meteo is used as the astronomy extension. The `/sky city` command obtains that city's sunrise, sunset, moonrise, moonset and moon phase through its forecast endpoint. It is a separate `handle_sky` function, so the extension remains modular and useful for planning observations without another API key.

### Client server diagram

```text
Webex user -> Webex cloud -> AstroBot Python client -> ISS / OpenWeather / Open-Meteo servers
                         <- formatted Webex response <- JSON HTTP responses
```

The Webex user sends a command; Webex stores it; AstroBot polls Webex then becomes a client to the external APIs. It parses their JSON and creates a new message with Webex `POST`. The API helper functions are the Model, output-formatting functions are the View, and command routing/polling is the Controller.

### Security evaluation

Secrets are read from `.env`, which is excluded by `.gitignore`; only `.env.example` is committed. Requests have timeouts, unsuccessful HTTP responses and invalid JSON are handled, user commands are checked, and polling happens every five seconds to reduce rate-limit risk. API credentials must never appear in commits, screenshots or the video.
