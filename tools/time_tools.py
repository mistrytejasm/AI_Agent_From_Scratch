import datetime
import urllib.request
import json
from tools.base import tool

@tool
def get_current_time() -> str:
    """Returns the current local date and time of the host system. Useful for identifying system time, date, or relative intervals."""
    now = datetime.datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S")

@tool
def get_world_time(iana_timezone: str) -> str:
    """Returns the exact current date and time from a public clock API for a specific IANA timezone identifier.
    
    Arguments:
    - iana_timezone: The IANA timezone identifier string (e.g. 'America/New_York', 'Asia/Kolkata', 'Europe/London', 'Asia/Tokyo', 'Australia/Sydney').
    """
    try:
        # Build TimeAPI.io endpoint
        url = f"https://timeapi.io/api/Time/current/zone?timeZone={iana_timezone}"
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            
        iso_time = data.get("dateTime")
        timezone_name = data.get("timeZone")
        
        # Clean microsecond decimals beyond 6 characters to prevent fromisoformat ValueErrors
        if "." in iso_time:
            main_part, micro_part = iso_time.split(".", 1)
            iso_time = f"{main_part}.{micro_part[:6]}"
            
        dt = datetime.datetime.fromisoformat(iso_time)
        formatted_time = dt.strftime("%A, %B %d, %Y, %I:%M:%S %p")
        
        return f"Current time in {timezone_name}: {formatted_time}"
    except Exception as e:
        return f"Error: Unable to fetch time for '{iana_timezone}' via API. Verify it is a valid key. Details: {e}"