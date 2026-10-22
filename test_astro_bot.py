"""Small offline tests for AstroBot command handling and error behaviour."""
import unittest
from unittest.mock import Mock, patch

import astro_bot


class AstroBotTests(unittest.TestCase):
    def test_epoch_conversion(self) -> None:
        self.assertEqual(astro_bot.epoch_to_utc(0), "1970-01-01 00:00:00 UTC")
        self.assertEqual(astro_bot.epoch_to_utc(None), "Unknown time")

    def test_stargazing_advice(self) -> None:
        clear = {"clouds": {"all": 10}, "weather": [{"main": "Clear"}]}
        rain = {"clouds": {"all": 90}, "weather": [{"main": "Rain"}]}
        self.assertIn("Good potential", astro_bot.stargazing_advice(clear))
        self.assertIn("Poor potential", astro_bot.stargazing_advice(rain))

    def test_weather_output_contains_time_and_safe_defaults(self) -> None:
        weather = {
            "dt": 0,
            "weather": [{"description": "clear sky", "main": "Clear"}],
            "main": {"temp": 8.5},
            "clouds": {"all": 10},
            "visibility": 9000,
        }
        result = astro_bot.format_weather("Hatfield, GB", weather)
        self.assertIn("Time: 1970-01-01 00:00:00 UTC", result)
        self.assertIn("Visibility: 9.0 km", result)
        self.assertIn("Good potential", result)

    def test_help_and_unknown_commands(self) -> None:
        self.assertIn("/weather", astro_bot.process_command("/help", "test-key"))
        self.assertEqual(
            astro_bot.process_command("/not-a-command", "test-key"),
            "Unknown command. Use /help.",
        )

    @patch("astro_bot.handle_weather", return_value="weather result")
    def test_weather_command_is_routed(self, mocked_weather: Mock) -> None:
        result = astro_bot.process_command("/weather Hatfield", "test-key")
        self.assertEqual(result, "weather result")
        mocked_weather.assert_called_once_with("Hatfield", "test-key")

    @patch("astro_bot.request_json", return_value=[])
    def test_unknown_city_returns_clear_error(self, _mocked_request: Mock) -> None:
        with self.assertRaisesRegex(astro_bot.ApiError, "could not find"):
            astro_bot.geocode_city("madeupplace", "test-key")

    @patch("astro_bot.request_json", return_value={"message": "failure"})
    def test_invalid_iss_response_is_rejected(self, _mocked_request: Mock) -> None:
        with self.assertRaisesRegex(astro_bot.ApiError, "successful position"):
            astro_bot.handle_iss("test-key")

    @patch("astro_bot.requests.request")
    def test_rate_limit_is_reported(self, mocked_request: Mock) -> None:
        response = Mock(status_code=429, headers={"Retry-After": "30"})
        mocked_request.return_value = response
        with self.assertRaisesRegex(astro_bot.ApiError, "Retrying after 30 seconds"):
            astro_bot.request_json("GET", "https://example.invalid")


if __name__ == "__main__":
    unittest.main()
