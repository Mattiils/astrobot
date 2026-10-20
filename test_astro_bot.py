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

    @patch("astro_bot.requests.request")
    def test_rate_limit_is_reported(self, mocked_request: Mock) -> None:
        response = Mock(status_code=429, headers={"Retry-After": "30"})
        mocked_request.return_value = response
        with self.assertRaisesRegex(astro_bot.ApiError, "Retrying after 30 seconds"):
            astro_bot.request_json("GET", "https://example.invalid")


if __name__ == "__main__":
    unittest.main()
