import pytest
from unittest.mock import Mock

from src.collectors.comment_stats import CommentStatsService
from src.common.errors import AppError


def _make_response(text: str, status: int = 200):
    resp = Mock()
    resp.status_code = status
    resp.text = text
    return resp


class TestCommentStatsService:
    def test_fetch_stats_parses_gender_and_age(self, mock_config, evidence):
        http_client = Mock()
        http_client.request.return_value = _make_response("cb({\"success\": true})")
        parse_jsonp = Mock(
            return_value={
                "success": True,
                "result": {
                    "commentCount": 240,
                    "commentByGender": [
                        {"gender": "M", "ratio": 82},
                        {"gender": "F", "ratio": 18},
                    ],
                    "commentByAge": [
                        {"age": "10", "ratio": 0},
                        {"age": "20", "ratio": 2},
                        {"age": "30", "ratio": 19},
                        {"age": "40", "ratio": 44},
                        {"age": "50", "ratio": 29},
                        {"age": "60", "ratio": 6},
                        {"age": "70", "ratio": 0},
                    ],
                },
            }
        )

        service = CommentStatsService(
            http_client=http_client,
            evidence=evidence,
            config=mock_config.collection.comment_stats,
            parse_jsonp=parse_jsonp,
        )

        record = service.fetch_stats("001", "0001", {"ticket": "news", "templateId": "default_society"})

        assert record["total_comments"] == 240
        assert record["gender"]["male"] == 82
        assert record["age"]["40"] == 44
        http_client.request.assert_called_once()

    def test_fetch_stats_raises_on_error_status(self, mock_config, evidence):
        http_client = Mock()
        http_client.request.return_value = _make_response("error", status=500)
        parse_jsonp = Mock()

        service = CommentStatsService(
            http_client=http_client,
            evidence=evidence,
            config=mock_config.collection.comment_stats,
            parse_jsonp=parse_jsonp,
        )

        with pytest.raises(AppError):
            service.fetch_stats("001", "0001", {})
