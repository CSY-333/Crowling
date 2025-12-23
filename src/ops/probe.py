import logging
import re
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class EndpointProbe:
    def __init__(self):
        self.known_configs = [
            # Config A (New API likely)
            {"ticket": "news", "templateId": "default_society"},
            # Config B (Fallback)
            {"ticket": "news", "templateId": "view_politics"},
        ]

    def get_candidate_configs(self, url: str, article_html: str) -> List[Dict[str, str]]:
        """
        Returns a list of configuration dictionaries to try, in order of priority:
        1. Auto-discovered parameters (if any)
        2. Known Config A
        3. Known Config B
        """
        candidates = []
        
        discovered = self.discover_parameters(url, article_html)
        if discovered:
            candidates.append(discovered)
            
        # Append fallbacks
        candidates.extend(self.known_configs)
        return candidates

    def discover_parameters(self, article_url: str, article_html: str) -> Optional[Dict[str, str]]:
        """
        Attempt to auto-discover parameters from HTML (ticket, templateId, objectId).
        Fallback to known configs if auto-discovery fails.
        """
        # 1. Auto-discovery (Regex/DOM)
        discovered = {} 
        
        if article_html:
            # Pattern 1: var _cv = "news"; var _templateId = "view_politics";
            # Note: Naver often uses `data-service-name` or JS vars.
            
            # Ticket (service name)
            ticket_match = re.search(r'serviceName\s*:\s*["\']([^"\']+)["\']', article_html)
            if not ticket_match:
                ticket_match = re.search(r'_cv\s*=\s*["\']([^"\']+)["\']', article_html)
            
            if ticket_match:
                discovered['ticket'] = ticket_match.group(1)
            else:
                discovered['ticket'] = 'news' # Default

            # Template ID
            # Look for `templateId = 'view_politics'` or similar
            tmpl_match = re.search(r'templateId\s*:\s*["\']([^"\']+)["\']', article_html)
            if not tmpl_match:
                tmpl_match = re.search(r'_templateId\s*=\s*["\']([^"\']+)["\']', article_html)
            
            if tmpl_match:
                discovered['templateId'] = tmpl_match.group(1)

            # Pool (cbox5 usually, but sometimes different)
            pool_match = re.search(r'pool\s*[:=]\s*["\']([^"\']+)["\']', article_html)
            if pool_match:
                discovered['pool'] = pool_match.group(1)

            # CV (Client Version or similar)
            cv_match = re.search(r'_cv\s*=\s*["\']([^"\']+)["\']', article_html)
            if cv_match:
                discovered['cv'] = cv_match.group(1)
                
            # Template (sometimes distinct from templateId)
            t_match = re.search(r'template\s*:\s*["\']([^"\']+)["\']', article_html)
            if t_match:
                discovered['template'] = t_match.group(1)

            # ObjectId is usually constructed from oid,aid, but sometimes explicit
            # We assume caller has oid,aid. If needed, we can extract `g_did` or `newsId` here.
        
        if discovered.get('ticket') and discovered.get('templateId'):
            logger.debug(f"Probe discovered params: {discovered}")
            return discovered
        return None

    def deep_validate_response(self, json_data: Dict[str, Any]) -> bool:
        """
        Validate schema integrity of comment response.
        Must contain 'result' -> 'commentList' -> [0] -> 'contents'/'regTime'
        """
        try:
            # Naver typical response: { "success": true, "result": { "commentList": [...] } }
            if not json_data.get('success', False):
                return False
                
            result = json_data.get('result', {})
            if 'commentList' not in result:
                # Sometimes it returns pageModel but empty list?
                # If commentList is missing entirely, it's suspicious unless count=0
                return False
                
            comment_list = result.get('commentList', [])
            if comment_list:
                first = comment_list[0]
                # Check for critical fields
                required = ['commentNo', 'contents', 'regTime'] 
                if not all(k in first for k in required):
                    logger.warning(f"Probe: Missing keys in comment: {first.keys()}")
                    return False
                    
            return True
        except Exception:
            return False
