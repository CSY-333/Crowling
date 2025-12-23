import pytest
from unittest.mock import MagicMock, ANY
from src.ops.health_check import HealthCheck

class TestHealthCheck:
    @pytest.fixture
    def mock_deps(self):
        searcher = MagicMock()
        parser = MagicMock()
        probe = MagicMock()
        fetcher = MagicMock()
        comment_parser = MagicMock()
        evidence = MagicMock()
        config = MagicMock()
        config.search.keywords = ["test_keyword"]
        
        return {
            "searcher": searcher,
            "parser": parser,
            "probe": probe,
            "comment_fetcher": fetcher,
            "comment_parser": comment_parser,
            "evidence": evidence,
            "config": config
        }

    def test_health_check_success(self, mock_deps):
        # Setup: 1 sample article found
        mock_deps["searcher"].search_keyword.return_value = [
            {"oid": "001", "aid": "0000001", "url": "http://Article1"}
        ]
        
        # 1. Metadata OK
        mock_deps["parser"].fetch_and_parse.return_value = {
            "status_code": "CRAWL-OK", 
            "_raw_html": "<html></html>"
        }
        
        # 2. Probe Param
        mock_deps["probe"].get_candidate_configs.return_value = [{"ticket": "news"}]
        
        # 3. Comment Fetch OK
        mock_deps["comment_fetcher"].fetch_page.return_value = '{"success":true}'
        mock_deps["comment_parser"].parse_jsonp.return_value = {"success": True}
        
        # 4. Probe Validation OK
        mock_deps["probe"].deep_validate_response.return_value = True
        
        hc = HealthCheck(
            config=mock_deps["config"],
            searcher=mock_deps["searcher"],
            parser=mock_deps["parser"],
            probe=mock_deps["probe"],
            comment_fetcher=mock_deps["comment_fetcher"],
            comment_parser=mock_deps["comment_parser"],
            evidence=mock_deps["evidence"]
        )
        
        assert hc.run_preflight_check() is True
        mock_deps["evidence"].log_failed_request.assert_not_called()

    def test_health_check_fail_metadata(self, mock_deps):
        mock_deps["searcher"].search_keyword.return_value = [
            {"oid": "001", "aid": "0000001", "url": "http://Article1"}
        ]
        # Metadata Fail
        mock_deps["parser"].fetch_and_parse.return_value = {"status_code": "FAIL-HTTP"}
        
        hc = HealthCheck(
            config=mock_deps["config"],
            searcher=mock_deps["searcher"],
            parser=mock_deps["parser"],
            probe=mock_deps["probe"],
            comment_fetcher=mock_deps["comment_fetcher"],
            comment_parser=mock_deps["comment_parser"],
            evidence=mock_deps["evidence"]
        )
        
        # 0 successes out of 1 sample -> Fail
        assert hc.run_preflight_check() is False

    def test_health_check_partial_success(self, mock_deps):
        # 3 samples
        mock_deps["searcher"].search_keyword.return_value = [
            {"oid": "1", "aid": "1", "url": "u1"},
            {"oid": "2", "aid": "2", "url": "u2"},
            {"oid": "3", "aid": "3", "url": "u3"},
        ]
        
        mock_deps["parser"].fetch_and_parse.return_value = {"status_code": "CRAWL-OK"}
        mock_deps["probe"].get_candidate_configs.return_value = [{"t": "n"}]
        mock_deps["comment_fetcher"].fetch_page.return_value = "{}"
        
        # Sample 1: Success
        # Sample 2: Fail (Schema)
        # Sample 3: Success
        mock_deps["probe"].deep_validate_response.side_effect = [True, False, True]
        
        hc = HealthCheck(
            config=mock_deps["config"],
            searcher=mock_deps["searcher"],
            parser=mock_deps["parser"],
            probe=mock_deps["probe"],
            comment_fetcher=mock_deps["comment_fetcher"],
            comment_parser=mock_deps["comment_parser"],
            evidence=mock_deps["evidence"]
        )
        
        # 2/3 Success -> Pass
        assert hc.run_preflight_check() is True
        
        # Check evidence logged for Sample 2 failure
        mock_deps["evidence"].log_failed_request.assert_called()
