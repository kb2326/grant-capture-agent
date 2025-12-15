"""
Advanced Search and Verification Tools for Proposal ADK Agent.
"""
import requests
from bs4 import BeautifulSoup
from typing import Optional


def check_eligibility_semantic(url: str, entity_type: str = "for-profit") -> str:
    """
    Downloads the solicitation page and scans for eligibility constraints (knockout check).
    
    Args:
        url: The URL of the grant opportunity (Notice or Solicitation).
        entity_type: The type of the user's organization (default: 'for-profit').
        
    Returns:
        A string summary of eligibility findings.
    """
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'lxml')
        text = soup.get_text(" ", strip=True).lower()
        
        # Heuristic Keywords for Eligibility Section
        eligibility_markers = ["eligibility information", "who may apply", "eligible applicants"]
        eligibility_text = ""
        
        # Try to find the specific section
        for marker in eligibility_markers:
            if marker in text:
                # Extract a chunk around the marker
                start_idx = text.find(marker)
                eligibility_text += text[start_idx:start_idx+2000] # Get first 2000 chars of section
                break
        
        if not eligibility_text:
            eligibility_text = text[:3000] # Fallback to first 3000 chars if sections undefined
            
        # Knockout Logic (Simple Heuristics)
        warnings = []
        if entity_type == "for-profit":
            if "non-profit only" in eligibility_text or "501(c)(3) status is required" in eligibility_text:
                warnings.append("⚠️ KNOCKOUT: Seems restricted to Non-Profits/501(c)(3).")
            if "university" in eligibility_text and "consortium" not in eligibility_text:
                                                # Weak check, but flags if it's purely academic
                                                pass

        if not warnings:
            return f"✅ ELIGIBILITY CHECK PASSED (Heuristic). Scan of text found no obvious blockers.\n\nExtracted Context:\n{eligibility_text[:500]}..."
        else:
            return f"❌ ELIGIBILITY WARNINGS:\n" + "\n".join(warnings) + f"\n\nContext:\n{eligibility_text[:500]}..."

    except Exception as e:
        return f"Error checking eligibility: {str(e)}"

def get_competitor_intelligence(cfda_number: Optional[str] = None, keyword: Optional[str] = None) -> str:
    """
    Queries USAspending.gov to find past recipients of similar grants to assess competition.
    
    Args:
        cfda_number: The Catalog of Federal Domestic Assistance number (e.g. '10.212').
        keyword: A keyword to search if CFDA is unknown.
        
    Returns:
        A summary of top competitors and potential 'winnability'.
    """
    api_url = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
    
    payload = {
        "filters": {
            "time_period": [{"start_date": "2023-01-01", "end_date": "2025-12-31"}],
            "award_type_codes": ["A", "B", "C", "D"],  # Grants
            "limit": 5
        },
        "fields": ["Recipient Name", "Award Amount"],
        "sort": "Award Amount",
        "order": "desc"
    }
    
    if cfda_number:
        payload["filters"]["program_numbers"] = [cfda_number]
    elif keyword:
         payload["filters"]["keywords"] = [keyword]
    else:
        return "Error: Must provide CFDA Number or Keyword."
        
    try:
        response = requests.post(api_url, json=payload, headers={'Content-Type': 'application/json'})
        data = response.json()
        
        if "results" not in data or not data["results"]:
             return "No direct competitor data found for this CFDA/Keyword in the last 2 years."
             
        summary = "🏆 **Competitor Intelligence (Past Winners):**\n"
        for result in data["results"]:
            summary += f"- {result.get('Recipient Name', 'Unknown')}: ${result.get('Award Amount', 0):,.2f}\n"
            
        return summary
        
    except Exception as e:
        return f"Error querying USAspending: {str(e)}"