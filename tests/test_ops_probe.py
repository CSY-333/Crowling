import pytest
from src.ops.probe import EndpointProbe

class TestEndpointProbe:
    @pytest.fixture
    def probe(self):
        return EndpointProbe()

    def test_discover_parameters_found(self, probe):
        html = """
        <script>
            var _cv = "news_service";
            var _templateId = "view_politics";
            var pool = "cbox99";
        </script>
        """
        params = probe.discover_parameters("http://url", html)
        assert params["ticket"] == "news_service"
        assert params["templateId"] == "view_politics"
        assert params["pool"] == "cbox99"

    def test_discover_parameters_service_name(self, probe):
        html = """
        serviceName: "sports",
        templateId: "view_sports",
        """
        params = probe.discover_parameters("http://url", html)
        assert params["ticket"] == "sports"
        assert params["templateId"] == "view_sports"

    def test_discover_parameters_missing(self, probe):
        html = "<html>No vars here</html>"
        params = probe.discover_parameters("http://url", html)
        # Should return None if ticket/templateId not found
        assert params is None

    def test_get_candidate_configs_priority(self, probe):
        html = """serviceName: "discovered", templateId: "discovered_tmpl" """
        candidates = probe.get_candidate_configs("http://url", html)
        
        # 1. Discovered
        assert candidates[0]["ticket"] == "discovered"
        assert candidates[0]["templateId"] == "discovered_tmpl"
        # 2. Know Config A
        assert candidates[1]["ticket"] == "news"
        # 3. Known Config B
        assert candidates[2]["ticket"] == "news"

    def test_deep_validate_response_success(self, probe):
        valid = {
            "success": True,
            "result": {
                "commentList": [
                    {"commentNo": "1", "contents": "c", "regTime": "t"}
                ]
            }
        }
        assert probe.deep_validate_response(valid) is True

    def test_deep_validate_response_failure(self, probe):
        # Case 1: success false
        assert probe.deep_validate_response({"success": False}) is False
        
        # Case 2: missing result
        assert probe.deep_validate_response({"success": True}) is False
        
        # Case 3: missing commentList key
        assert probe.deep_validate_response({"success": True, "result": {}}) is False
        
        # Case 4: item missing keys
        invalid_item = {
            "success": True,
            "result": {
                "commentList": [{"commentNo": "1"}] # missing contents/regTime
            }
        }
        assert probe.deep_validate_response(invalid_item) is False
