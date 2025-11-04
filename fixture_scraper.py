import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timedelta, date

# --- CONFIGURATION ---

# 1. URLs to Scrape: Replace these with the *specific* URLs for the leagues you want.
# You will likely need one URL for each division page (e.g., Men's Prem, Women's Div 1, etc.)
LEAGUES_11S = [
    "https://www.betterfootball.co.nz/fixtures-and-standings/mens-premier-11s/",
    "https://www.betterfootball.co.nz/fixtures-and-standings/mens-division-1-11s/",
    # Add all other 11s league URLs here
]

# 2. URLs for 7s/5s Leagues (for 'I'm Available' boxes)
# The script will only scrape these to find the date/day they are played.
LEAGUES_7S_5S = [
    "https://www.betterfootball.co.nz/fixtures-and-standings/mixed-7s-tuesday/",
    "https://www.betterfootball.co.nz/fixtures-and-standings/mens-5s-wednesday/",
    # Add all other 7s/5s league URLs here
]

# 3. HTML Selectors: These are educated guesses for the structure.
# If the script fails, these are the first things to check on the website's source code.
CSS_SELECTORS = {
    # Selector for the main table container (e.g., a div or a table ID)
    "FIXTURE_TABLE": "#tablepress-20", # Assumed table ID for the fixture list
    # Selector for the rows within the table (<tr>)
    "FIXTURE_ROWS": "tbody tr", 
    # Selectors for data within each row (td:nth-child(X))
    "DATA_COLUMNS": {
        "Date": 1,
        "Time": 2,
        "Home": 3,
        "Away": 4,
        "Pitch": 5,
        "League": 6, # Assuming league name might be in the first column or needs to be derived
    }
}

# *** CRITICAL FIX: The HTML file looks for 'fixtures.json', so we match that name. ***
OUTPUT_FILE = 'fixtures.json' 
# --- END CONFIGURATION ---

def get_target_date_range():
    """Calculates the date range: Upcoming Saturday to the following Thursday."""
    today = date.today()
    
    # 5 is Saturday (Mon=0, Tue=1, ... Sat=5)
    days_until_sat = (5 - today.weekday() + 7) % 7 
    next_sat = today + timedelta(days=days_until_sat)
    
    # Thursday is 6 days after Saturday
    next_thu = next_sat + timedelta(days=6)
    
    print(f"Targeting fixtures from {next_sat} to {next_thu}")
    return next_sat, next_thu

def is_date_in_range(fixture_date_str, start_date, end_date):
    """Checks if a fixture date falls within the Saturday-to-Thursday window."""
    try:
        # Fixture dates often come in DD/MM/YYYY or similar. We must parse it.
        # Assuming DD/MM/YYYY from common NZ format. Adjust if necessary.
        fixture_date = datetime.strptime(fixture_date_str, '%d/%m/%Y').date()
        return start_date <= fixture_date <= end_date
    except ValueError:
        try:
            # Try YYYY-MM-DD format as a fallback
            fixture_date = datetime.strptime(fixture_date_str, '%Y-%m-%d').date()
            return start_date <= fixture_date <= end_date
        except ValueError:
            return False

def scrape_11s_league(url, start_date, end_date):
    """Scrapes a single 11s league page for specific fixtures."""
    fixtures = []
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        soup = BeautifulSoup(response.content, 'html.parser')

        # Identify the league name from the URL or page title
        league_name = url.split('/')[-2].replace('-', ' ').title() 
        print(f"Scraping 11s league: {league_name}")

        table = soup.select_one(CSS_SELECTORS["FIXTURE_TABLE"])
        if not table:
            print(f"Warning: Could not find fixture table at {url}. Check selector.")
            return []

        rows = table.select(CSS_SELECTORS["FIXTURE_ROWS"])
        
        for row in rows:
            # We assume a fixed column order for simplicity and stability
            date_col = row.select_one(f'td:nth-child({CSS_SELECTORS["DATA_COLUMNS"]["Date"]})')
            
            if not date_col or not date_col.text.strip():
                continue # Skip empty rows

            date_str = date_col.text.strip()
            
            if is_date_in_range(date_str, start_date, end_date):
                time_str = row.select_one(f'td:nth-child({CSS_SELECTORS["DATA_COLUMNS"]["Time"]})').text.strip()
                home_team = row.select_one(f'td:nth-child({CSS_SELECTORS["DATA_COLUMNS"]["Home"]})').text.strip()
                away_team = row.select_one(f'td:nth-child({CSS_SELECTORS["DATA_COLUMNS"]["Away"]})').text.strip()
                pitch_name = row.select_one(f'td:nth-child({CSS_SELECTORS["DATA_COLUMNS"]["Pitch"]})').text.strip()

                fixtures.append({
                    "date": date_str,
                    "time": time_str,
                    "home": home_team,
                    "away": away_team,
                    "pitch": pitch_name,
                    "league": league_name,
                })
        
        print(f"Found {len(fixtures)} valid fixtures in {league_name}.")
        return fixtures

    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred while processing {url}: {e}")
        return []

def create_night_availability(url, start_date, end_date):
    """Generates a single 'I'm Available' placeholder for a 7s/5s league night."""
    
    league_name = url.split('/')[-2].replace('-', ' ').title() 
    print(f"Processing 7s/5s league: {league_name}")

    # Step 1: Determine the specific day(s) this league plays on
    # This often requires scraping the page title or intro text for 'Tuesday', 'Wednesday', etc.
    # For simplicity, we'll assume the league name in the URL is correct (e.g., "mixed-7s-tuesday")
    
    day_name = league_name.split(' ')[-1].strip()
    day_map = {'tuesday': 1, 'wednesday': 2, 'thursday': 3, 'monday': 0}
    
    target_weekday = day_map.get(day_name.lower())
    
    if target_weekday is None:
        print(f"Warning: Could not determine play day for {league_name}. Skipping.")
        return []

    # Step 2: Find the date for that weekday within the target range
    
    # We only care about the *one* day in the week they play.
    availability_fixtures = []
    
    # Iterate through the week, starting from the target Saturday
    current_date = start_date
    while current_date <= end_date:
        if current_date.weekday() == target_weekday:
            # Found the night they play this week
            availability_fixtures.append({
                "date": current_date.strftime('%Y-%m-%d'),
                "time": "Night",
                "home": league_name,
                "away": "OPEN NIGHT AVAILABILITY",
                "pitch": "Multiple",
                "league": "Night Referees",
            })
            break
        current_date += timedelta(days=1)

    return availability_fixtures


def main_scraper():
    """Main function to orchestrate the entire scraping process."""
    
    target_sat, target_thu = get_target_date_range()
    all_fixtures = []

    # 1. Scrape 11s Fixtures
    print("\n--- Starting 11s Fixture Scraping ---")
    for url in LEAGUES_11S:
        all_fixtures.extend(scrape_11s_league(url, target_sat, target_thu))

    # 2. Create 7s/5s Night Availability Items
    print("\n--- Starting 7s/5s Availability Generation ---")
    for url in LEAGUES_7S_5S:
        all_fixtures.extend(create_night_availability(url, target_sat, target_thu))

    # 3. Final Processing
    print("\n--- Processing Complete ---")
    
    if not all_fixtures:
        print("No fixtures found in the target date range.")
        output_json = "[]"
    else:
        # Convert to the JSON format needed for the scheduler's ingestion box
        output_json = json.dumps(all_fixtures, indent=4)
        
        # Save to file
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write(output_json)

        print(f"Successfully generated {len(all_fixtures)} items.")
        print(f"JSON output saved to '{OUTPUT_FILE}'.")
    
    return output_json


if __name__ == "__main__":
    # Ensure you install the required libraries: pip install requests beautifulsoup4
    print("Starting automated fixture data pull...")
    main_scraper()
