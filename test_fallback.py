"""Test script to verify API key fallback functionality in OddsFetcher."""
import os
import sys
import unittest
from unittest.mock import MagicMock

# Fix path to import lib
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Inject mock requests module before importing odds_fetcher to avoid dependency issues
mock_requests = MagicMock()
sys.modules['requests'] = mock_requests

from lib import odds_fetcher
from lib.odds_fetcher import OddsFetcher

class TestOddsFetcherFallback(unittest.TestCase):
    def setUp(self):
        # Reset global states
        odds_fetcher._cache.clear()
        odds_fetcher._exhausted_keys.clear()
        odds_fetcher.ODDS_API_KEY = "PRIMARY_MOCK_KEY"
        odds_fetcher.ODDS_API_KEY_SEGUNDO = "SECONDARY_MOCK_KEY"
        odds_fetcher._active_api_key = "PRIMARY_MOCK_KEY"
        mock_requests.reset_mock()

    def test_fallback_success(self):
        # Set up mock responses
        # First call to primary key returns 429 Rate Limit
        # Second call to secondary key returns 200 Success
        response_primary = MagicMock()
        response_primary.status_code = 429
        response_primary.text = "Rate limit exceeded"
        response_primary.headers = {}

        response_secondary = MagicMock()
        response_secondary.status_code = 200
        response_secondary.headers = {"x-requests-remaining": "99"}
        # Return mock JSON structure for match
        response_secondary.json.return_value = [
            {
                "id": "match_123",
                "sport_key": "soccer_fifa_world_cup",
                "sport_title": "World Cup 2026",
                "commence_time": "2026-06-29T20:00:00Z",
                "home_team": "Brasil",
                "away_team": "Francia",
                "bookmakers": [
                    {
                        "key": "bet365",
                        "title": "Bet365",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Brasil", "price": 2.10},
                                    {"name": "Draw", "price": 3.40},
                                    {"name": "Francia", "price": 3.10}
                                ]
                            }
                        ]
                    }
                ]
            }
        ]

        mock_requests.get.side_effect = [response_primary, response_secondary]

        # Initialize fetcher (should use primary key)
        fetcher = OddsFetcher()
        self.assertEqual(fetcher.api_key, "PRIMARY_MOCK_KEY")

        # Run get_matches (this should trigger the fallback)
        matches = fetcher.get_matches()

        # Check that we tried both keys
        self.assertEqual(mock_requests.get.call_count, 2)
        
        # Verify the calls had the correct API keys
        first_call_args = mock_requests.get.call_args_list[0][1]
        second_call_args = mock_requests.get.call_args_list[1][1]
        
        self.assertEqual(first_call_args['params']['apiKey'], "PRIMARY_MOCK_KEY")
        self.assertEqual(second_call_args['params']['apiKey'], "SECONDARY_MOCK_KEY")

        # Verify instance and global active state were updated
        self.assertEqual(fetcher.api_key, "SECONDARY_MOCK_KEY")
        self.assertEqual(odds_fetcher._active_api_key, "SECONDARY_MOCK_KEY")
        self.assertIn("PRIMARY_MOCK_KEY", odds_fetcher._exhausted_keys)

        # Check matches returned are normalized
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['id'], "match_123")
        self.assertIn("bet365", matches[0]['bookmakers'])

    def test_both_keys_exhausted(self):
        # Both keys return 429 / 403
        response_primary = MagicMock()
        response_primary.status_code = 429
        response_primary.text = "Rate limit exceeded"
        response_primary.headers = {}

        response_secondary = MagicMock()
        response_secondary.status_code = 403
        response_secondary.text = "OUT_OF_USAGE_CREDITS"
        response_secondary.headers = {}

        mock_requests.get.side_effect = [response_primary, response_secondary]

        fetcher = OddsFetcher()
        matches = fetcher.get_matches()

        # Both keys should have been tried and marked as exhausted
        self.assertEqual(mock_requests.get.call_count, 2)
        self.assertIn("PRIMARY_MOCK_KEY", odds_fetcher._exhausted_keys)
        self.assertIn("SECONDARY_MOCK_KEY", odds_fetcher._exhausted_keys)
        
        # Should fallback to mock data since all keys failed
        self.assertTrue(fetcher.is_mock)

        # A new instance should immediately fail over to mock data without calling API
        mock_requests.get.reset_mock()
        fetcher2 = OddsFetcher()
        self.assertTrue(fetcher2.is_mock)
        matches2 = fetcher2.get_matches()
        mock_requests.get.assert_not_called()

if __name__ == "__main__":
    unittest.main()
