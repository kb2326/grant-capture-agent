
import pytest
from my_agent.tools.advanced_search import check_eligibility_semantic, get_competitor_intelligence
from my_agent.tools.capabilities import get_default_capabilities

def test_capabilities_load():
    caps = get_default_capabilities()
    assert isinstance(caps, str)
    # assert len(caps) > 0 # capabilities.txt might be empty initially

def test_competitor_intel_structure():
    # We mock the request to avoid actual API calls during basic logic test
    # But for now let's just check the function signature and trivial error cases
    result = get_competitor_intelligence(cfda_number=None, keyword=None)
    assert "Error: Must provide" in result

def test_imports():
    from my_agent.tools.apis import grants_toolset
    assert grants_toolset is not None
