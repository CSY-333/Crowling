import pytest
import json
from unittest.mock import MagicMock, Mock
from src.collectors.comment_collector import CommentCollector
from src.collectors.comment_parser import CommentParser, JSONPParseError, SchemaMismatchError
from src.collectors.comment_fetcher import CommentFetcher
from src.storage.repository import CommentRepository
from src.privacy.hashing import PrivacyHasher

class TestCommentCollector:
    @pytest.fixture
    def collector(self, mock_config):
        fetcher = Mock(spec=CommentFetcher)
        parser = Mock(spec=CommentParser)
        repo = Mock(spec=CommentRepository)
        repo.is_article_completed.return_value = False
        return CommentCollector(mock_config, fetcher, parser, repo, "2023-01-01T00:00:00")

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
        collector.parser.extract_comments.return_value = [{"id": 1}]
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
