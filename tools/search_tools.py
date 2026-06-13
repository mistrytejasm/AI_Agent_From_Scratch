import urllib.request
import re
from tavily import TavilyClient
from config.settings import settings
from tools.base import tool

@tool
def search_web(
    query: str, 
    search_depth: str = "basic", 
    topic: str = "general", 
    time_range: str = "none"
) -> str:
    """Searches the web using Tavily. Grabs optimized text and citations.
    
    Arguments:
    - query: The target search query terms.
    - search_depth: 'basic' or 'advanced' (use 'advanced' for complex queries requiring deep research).
    - topic: 'general' or 'news' (use 'news' for current events, news, or topics happening today/recently).
    - time_range: 'day' (past 24h), 'week' (past 7 days), 'month' (past 30 days), or 'none' (default, no date filter).
    """
    try:
        client = TavilyClient(api_key=settings.tavily_api_key)
        
        # Base query arguments
        api_args = {
            "query": query,
            "max_results": 5,
            "search_depth": search_depth,
            "topic": topic
        }
        
        # Apply time filter if not set to 'none'
        if time_range and time_range.lower() != "none":
            mapping = {
                "day": "d",
                "d": "d",
                "week": "w",
                "w": "w",
                "month": "m",
                "m": "m",
                "year": "y",
                "y": "y"
            }
            api_args["time_range"] = mapping.get(time_range.lower(), "w")
            
        try:
            # Attempt search with LLM arguments
            response = client.search(**api_args)
        except Exception as api_err:
            # Fallback to 'general' search if 'news' fails (free tier key restriction)
            if topic == "news":
                api_args["topic"] = "general"
                response = client.search(**api_args)
            else:
                raise api_err

        results = response.get("results", [])
        if not results:
            return "No search results found."
        
        output = []
        for r in results:
            output.append(f"Title: {r['title']}\nURL: {r['url']}\nContent: {r['content']}\n---")
        return "\n".join(output)
        
    except Exception as e:
        return f"Error performing web search with Tavily: {e}"

@tool
def fetch_webpage(url: str) -> str:
    """Fetches raw text content from a specific URL and removes HTML formatting. Helpful for reading documentation or articles."""
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8', errors='ignore')
            
        # Strip HTML details
        html = re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', '', html)
        html = re.sub(r'<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>', '', html)
        text = re.sub(r'<[^>]+>', ' ', html)
        
        # Clean whitespaces
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        if len(text) > 4000:
            return text[:4000] + "\n\n[Content Truncated due to length]"
        return text
    except Exception as e:
        return f"Error loading webpage: {e}"