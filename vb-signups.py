#!/usr/bin/python3

import json
import requests
import time
from datetime import datetime

current_date = datetime.now().strftime("%m-%d-%Y")
PREVIOUS_RESULTS_FILE = "previous_results.json"
RETRY_ATTEMPTS = 3
RETRY_DELAY = 5  # seconds
PLAY_LEVEL="Recreational"
DAY="friday".lower()
SPORT='47' # indoor volleyball
STATUS='sign_up'
API_URL = f"https://api.clevelandplays.com/api/leagues/all-leagues/{SPORT}?status={STATUS}&limit=500&page=1&search=&indv=&page_type=sign_up&current_date={current_date}"



def fetch_league_data():
    for attempt in range(RETRY_ATTEMPTS):
        try:
            response = requests.get(API_URL, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"API request failed (attempt {attempt + 1}): {e}")
            time.sleep(RETRY_DELAY * (2 ** attempt))
    print("Failed to fetch data after multiple attempts.")
    return None


def load_previous_results():
    try:
        with open(PREVIOUS_RESULTS_FILE, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_results(results):
    with open(PREVIOUS_RESULTS_FILE, "w") as file:
        json.dump(results, file, indent=4)


def check_for_updates(new_data, old_data):
    old_leagues = {league["name"]: league for league in old_data}
    new_leagues = {league["name"]: league for league in new_data}

    print("Open leagues:")
    for league_name, league in new_leagues.items():
        if league_name not in old_leagues or old_leagues[league_name]["status"] == STATUS:
            print(f"(Spots left: {league['open_slots']}): {league['name']} signup: (https://users.clevelandplays.com/league/team-registration/{league['id']}/{league['sport']['id']})")

def day_of_week(d):
  date_obj = datetime.strptime(d, "%Y-%m-%d")
  return date_obj.strftime("%A").lower()

def refine_league(league):
  league['day_of_week'] = day_of_week(league['start_date'])
  league['is_full'] = league['teams'] >= league['team_size']
  league['open_slots'] = league['team_size'] - league['teams']
  return league

def main():
    new_data = fetch_league_data()
    if new_data is None:
        return

    data = [refine_league(league) for league in new_data['data']['rows']]

    filtered_data = [league for league in data if league['day_of_week'] == DAY and league["play_level"] == PLAY_LEVEL]

    print(filtered_data)

    old_data = load_previous_results()

    check_for_updates(filtered_data, old_data)
    save_results(filtered_data)

if __name__ == "__main__":
    main()