import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timedelta

# --- Configuration ---
# You can add or remove URLs here. These are the two primary ones for 11-a-side fixtures.
TARGET_URLS = [
    "https://www.betterfootball.co.nz/fixtures-and-standings/saturday-11s-mens-fixtures-202526/", 
    "https://www.betterfootball.co.nz/fixtures-and-standings/sunday-league-11s-202526-fixtures/" 
]
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
MONTH_MAP = { "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12 }

def calculate_date_range():
    """Calculates the target date range: current Saturday to next Thursday."""
    today = datetime.now().date()
    
    # Python weekday(): 0=Monday, 5=Saturday, 6=Sunday
    days_until_saturday = (5 - today.weekday() + 7) % 7
    
    if today.weekday() == 5: # If today is Saturday, start today
        start_date = today
    else:
        # Otherwise, calculate the upcoming Saturday
        start_date = today + timedelta(days=days_until_saturday)
        
    # The end date is the Thursday after the calculated Saturday
    end_date = start_date + timedelta(days=5) # Saturday + 5 days = Thursday

    print(f"Targeting fixtures from {start_date.isoformat()} (Saturday) to {end_date.isoformat()} (Thursday).")
    return start_date, end_date

def convert_12hr_to_24hr(time_str):
    """Converts 'HH:MM AM/PM' to 'HH:MM' (24-hour format)."""
    try:
        if 'AM' in time_str.upper() or 'PM' in time_str.upper():
            dt_object = datetime.strptime(time_str, '%I:%M %p')
        else:
            # Assume 24-hour format if no AM/PM indicator is present
            dt_object = datetime.strptime(time_str, '%H:%M')
        return dt_object.strftime('%H:%M')
    except ValueError:
        return None

def format_date_to_iso(date_str_raw):
    """Converts 'DD Mon YYYY' to 'YYYY-MM-DD'."""
    date_header_match = date_str_raw.match(r'(\d{1,2})\s+([a-zA-Z]{3})\s+(\d{4})')
    if not date_header_match:
        return None, None
        
    day = int(date_header_match.group(1))
    month_str = date_header_match.group(2).lower()
    year = int(date_header_match.group(3))
    
    month_index = MONTH_MAP.get(month_str)
    
    if month_index:
        try:
            fixture_date_obj = datetime(year, month_index, day).date()
            return fixture_date_obj, fixture_date_obj.isoformat()
        except ValueError:
            return None, None
            
    return None, None

def scrape_fixtures(start_date, end_date):
    """Fetches, parses, and filters fixtures from the target URLs."""
    all_fixtures = []
    
    for url in TARGET_URLS:
        print(f"\n--- Processing URL: {url} ---")
        league_from_url = "Saturday 11s" if "saturday" in url else ("Sunday 11s" if "sunday" in url else "Unknown 11s")

        try:
            response = requests.get(url, headers=HEADERS)
            response.raise_for_status() 
            soup = BeautifulSoup(response.content, 'html.parser')

        except requests.exceptions.RequestException as e:
            print(f"Error fetching {url}: {e}")
            continue

        # Initialize stateful date tracker
        current_date_iso = None
        
        # Look for table elements, as the fixtures are contained within them.
        tables = soup.select('table') 

        for table in tables:
            rows = table.find_all('tr')

            for row in rows:
                cols = row.find_all(['td', 'th'])
                if not cols:
                    continue

                first_col_text = cols[0].get_text(strip=True)

                # 1. Check for Date Header Row (e.g., "04 Nov 2025")
                date_header_match = datetime.strptime
                try:
                    # Attempt to parse as a date header
                    dt_obj = datetime.strptime(first_col_text, '%d %b %Y')
                    current_date_obj = dt_obj.date()
                    current_date_iso = current_date_obj.isoformat()
                    print(f"Found Date Header: {current_date_iso}")
                    continue
                except ValueError:
                    # Not a date header, continue to fixture check
                    pass 
                
                # 2. Check for Fixture Row (Structure: Home, vs, Away, Venue, Pitch, Time)
                if current_date_iso and len(cols) >= 6:
                    home_team = cols[0].get_text(strip=True)
                    away_team = cols[2].get_text(strip=True) 
                    venue = cols[3].get_text(strip=True)
                    pitch = cols[4].get_text(strip=True)
                    time_str_raw = cols[5].get_text(strip=True)

                    # Basic validation and filter
                    if not home_team or not away_team or not time_str_raw:
                        continue
                    
                    if home_team.lower() == 'bye' or away_team.lower() == 'bye':
                         # print(f"Skipping 'Bye' fixture: {home_team} vs {away_team}")
                         continue
                         
                    # --- Time Conversion (12hr to 24hr) ---
                    time_24hr = convert_12hr_to_24hr(time_str_raw)

                    # --- Date Range Filtering ---
                    if start_date <= current_date_obj <= end_date and time_24hr:
                        
                        all_fixtures.append({
                            "date": current_date_iso, 
                            "time": time_24hr, 
                            "home": home_team, 
                            "away": away_team, 
                            "pitch": venue, # Venue is the location name (St Pats, Boyd Wilson)
                            "league": league_from_url 
                        })
                    # else:
                        # print(f"Skipping fixture outside range/invalid time: {home_team} vs {away_team} on {current_date_iso} at {time_str_raw}")


    print(f"\n✅ Total fixtures found within the target range: {len(all_fixtures)}")
    return all_fixtures

def save_fixtures_to_json(fixtures):
    """Saves the extracted fixtures list to a JSON file."""
    try:
        with open('fixtures.json', 'w', encoding='utf-8') as f:
            json.dump(fixtures, f, indent=4, ensure_ascii=False)
        print("Successfully wrote fixtures to fixtures.json")
    except Exception as e:
        print(f"Error saving file: {e}")

if __name__ == '__main__':
    start_date, end_date = calculate_date_range()
    
    # Execute the scraping function
    weekly_fixtures = scrape_fixtures(start_date, end_date)
    
    # Save the results (This is the file the GitHub Action commits)
    save_fixtures_to_json(weekly_fixtures)
