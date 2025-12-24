import pytest
import json
from unittest.mock import MagicMock, Mock, ANY
from src.collectors.comment_collector import CommentCollector
from src.collectors.comment_parser import CommentParser, JSONPParseError, SchemaMismatchError
from src.collectors.comment_fetcher import CommentFetcher
from src.storage.repository import CommentRepository
from src.privacy.hashing import PrivacyHasher
from src.ops.structural import FailureKind, StructuralError

class TestCommentCollector:
    @pytest.fixture
    def collector(self, mock_config):
        fetcher = Mock(spec=CommentFetcher)
        parser = Mock(spec=CommentParser)
        parser.extract_total_count.return_value = 0
        repo = Mock(spec=CommentRepository)
        repo.is_article_completed.return_value = False
        stats_service = Mock()
        collector = CommentCollector(
            mock_config,
            fetcher,
            parser,
            repo,
            "2023-01-01T00:00:00",
            stats_service=stats_service,
        )
        collector.stats_service = stats_service
        return collector

    def test_parse_jsonp_valid(self, mock_config):
        parser = CommentParser(mock_config, PrivacyHasher("salt"))
        # Plain JSON
        assert parser.parse_jsonp('{"a": 1}') == {"a": 1}
        # Callback wrapper
        assert parser.parse_jsonp('cb({"a": 1});') == {"a": 1}
        # Weird spacing
        assert parser.parse_jsonp('  _callback (  {"a": 1}  )  ') == {"a": 1}

    def test_parse_jsonp_invalid(self, mock_config):
        parser = CommentParser(mock_config, PrivacyHasher("salt"))
        with pytest.raises(JSONPParseError):
            parser.parse_jsonp("<html>Error</html>")
        with pytest.raises(JSONPParseError):
            parser.parse_jsonp("")

    def test_persist_comments_delegates_to_repo(self, collector):
        comments = [
            {
                "commentNo": "100",
                "contents": "Test",
                "userId": "user1hash",
                "regTime": "2023-01-01 12:00:00",
                "sympathyCount": 10
            }
        ]
        collector.parser.extract_comments.return_value = comments
        collector.parser.to_record.return_value = {"comment_no": "100"}
        collector.repository.persist_comments.return_value = 1
        collector.fetcher.fetch.return_value = "{}"
        collector.parser.parse_jsonp.return_value = {}
        collector.parser.extract_cursor.return_value = None

        written = collector.collect_article("oid", "aid", {})
        assert written == 1
        collector.repository.persist_comments.assert_called_once()

    def test_pagination_stops_on_duplicate_cursor(self, collector):
        # Setup mocks
        collector.fetcher.fetch.return_value = "{}"
        collector.parser.parse_jsonp.return_value = {}
        collector.parser.extract_comments.return_value = [
            {"commentNo": "1", "contents": "c", "regTime": "now"}
        ]
        # Return same cursor twice
        collector.parser.extract_cursor.side_effect = ["CURSOR_A", "CURSOR_A"]
        collector.repository.persist_comments.return_value = 1
        
        count = collector.collect_article("oid", "aid", {})
        # Should process page 1, see Cursor A.
        # Process page 2, see Cursor A again -> Stop.
        # Total comments 2.
        assert count == 2
        assert collector.fetcher.fetch.call_count == 2

    def test_to_record_hashes_identifier(self, mock_config):
        parser = CommentParser(mock_config, PrivacyHasher("salt"))
        record = parser.to_record(
            {
                "commentNo": "1",
                "contents": "hi",
                "userId": "author",
                "regTime": "1700000000",
                "sympathyCount": 1,
            },
            depth=0,
            parent=None,
            snapshot_at="2023-01-01T00:00:00",
        )
        assert record["author_hash"] is not None
        assert record["author_raw"] is None

    def test_structural_failure_delegation(self, collector):
        # Setup: Mock structural detector
        mock_detector = Mock()
        collector.structural_detector = mock_detector
        
        # Setup: Fetcher returns junk
        collector.fetcher.fetch.return_value = "<html>Error</html>"
        collector.parser.parse_jsonp.side_effect = JSONPParseError("Bad JSONP")
        
        # Run
        with pytest.raises(JSONPParseError):
            collector.collect_article("oid", "aid", {})
            
        # Verify failure was recorded with context
        mock_detector.record_failure.assert_called_with(
            "[WARN/PARSE] Bad JSONP",
            kind=FailureKind.PARSE,
            context=ANY,
        )

    def test_collect_article_triggers_stats_when_threshold_met(self, collector):
        collector.config.collection.comment_stats.min_comments = 1
        collector.parser.extract_total_count.return_value = 150
        collector.parser.extract_comments.side_effect = [
            [{"commentNo": "1", "contents": "c", "regTime": "now"}],
            [],
        ]
        collector.parser.to_record.return_value = {"comment_no": "1"}
        collector.parser.extract_cursor.return_value = None
        collector.repository.persist_comments.return_value = 1
        collector.fetcher.fetch.return_value = "{}"
        collector.parser.parse_jsonp.return_value = {}
        collector.stats_service.fetch_stats.return_value = {
            "total_comments": 150,
            "gender": {"male": 82.0, "female": 18.0},
            "age": {"10": 0.0}
        }

        collector.collect_article("oid", "aid", {"ticket": "news"})

        collector.stats_service.fetch_stats.assert_called_once_with("oid", "aid", {"ticket": "news"})
        collector.repository.persist_comment_stats.assert_called_once()

    def test_collect_article_skips_stats_when_under_threshold(self, collector):
        collector.config.collection.comment_stats.min_comments = 200
        collector.parser.extract_total_count.return_value = 150
        collector.parser.extract_comments.return_value = [
            {"commentNo": "1", "contents": "c", "regTime": "now"}
        ]
        collector.parser.to_record.return_value = {"comment_no": "1"}
        collector.repository.persist_comments.return_value = 1
        collector.fetcher.fetch.return_value = "{}"
        collector.parser.parse_jsonp.return_value = {}
        collector.parser.extract_cursor.return_value = None

        collector.collect_article("oid", "aid", {})

        collector.stats_service.fetch_stats.assert_not_called()
        collector.repository.persist_comment_stats.assert_not_called()

    def test_missing_required_comment_field_triggers_structural(self, collector):
        collector.fetcher.fetch.return_value = "{}"
        collector.parser.parse_jsonp.return_value = {}
        collector.parser.extract_comments.return_value = [
            {"commentNo": "", "contents": "c", "regTime": "now"}
        ]

        with pytest.raises(StructuralError):
            collector.collect_article("oid", "aid", {})

