from dataclasses import dataclass

from src.collectors.article_parser import ArticleParser


@dataclass
class StubResponse:
    status_code: int = 200
    text: str = ""


class StubHttpClient:
    def __init__(self, response: StubResponse):
        self.response = response
        self.requested = []

    def request(self, method, url, **kwargs):
        self.requested.append((method, url, kwargs))
        return self.response


def test_fetch_and_parse_prefers_json_ld():
    html = """
    <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "NewsArticle",
                "headline": "JSON Headline",
                "datePublished": "2025-01-01T00:00:00+09:00",
                "dateModified": "2025-01-01T00:30:00+09:00",
                "articleSection": "Tech",
                "author": {"name": "Reporter A"}
            }
            </script>
        </head>
        <body>
            <a class="media_end_head_top_logo"><img title="Press Name"/></a>
            <div id="dic_area">Body text<span class="end_photo_org">ignore</span></div>
        </body>
    </html>
    """
    parser = ArticleParser(StubHttpClient(StubResponse(text=html)))

    result = parser.fetch_and_parse("https://news.example.com/article")

    assert result["status_code"] == "CRAWL-OK"
    assert result["title"] == "JSON Headline"
    assert result["published_at"] == "2025-01-01T00:00:00+09:00"
    assert result["reporter"] == "Reporter A"
    assert result["section"] == "Tech"
    assert result["press"] == "Press Name"
    assert result["body"] == "Body text"
    assert result["body_length"] == len("Body text")


def test_fetch_and_parse_handles_http_errors():
    parser = ArticleParser(StubHttpClient(StubResponse(status_code=500)))

    result = parser.fetch_and_parse("https://news.example.com/article")

    assert result["status_code"] == "FAIL-HTTP"
    assert result["error_code"] == "500"
