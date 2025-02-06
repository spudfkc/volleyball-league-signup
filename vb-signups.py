import asyncio
import json
import os
import requests
import time
from datetime import datetime
from loguru import logger
from discord.ext import tasks
import discord
from dotenv import load_dotenv

current_date = datetime.now().strftime("%m-%d-%Y")
PREVIOUS_RESULTS_FILE = "previous_results.json"
RETRY_ATTEMPTS = 3
RETRY_DELAY = 5  # seconds
PLAY_LEVEL="recreational".lower()
DAY='monday'    # set to day of the week if you want to filter. e.x. 'monday'
SPORT='47' # indoor volleyball
STATUS='sign_up'
API_URL = f"https://api.clevelandplays.com/api/leagues/all-leagues/{SPORT}?status={STATUS}&limit=500&page=1&search=&indv=&page_type=sign_up&current_date={current_date}"
discord_enabled = True


class DiscordClient(discord.Client):
    task = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def setup_hook(self) -> None:
        # create the background task and run it in the background
        self.bg_task = self.loop.create_task(self.my_background_task())

    async def on_ready(self):
        logger.info(f'Logged on as {self.user}')

    async def my_background_task(self):
        await self.wait_until_ready()
        await asyncio.sleep(5)
        logger.info(f'starting background task w channel {os.environ["DISCORD_CHANNEL_ID"]}')
        counter = 0
        channel = await self.fetch_channel(os.environ["DISCORD_CHANNEL_ID"])
        logger.info(f'channel: {channel}')
        while not self.is_closed():
            counter += 1
            logger.info(f'sending: {counter}')
            leagues = self.task.run()
            for league in leagues:
                await channel.send(f"(Spots left: {league['open_slots']}): {league['name']} signup: ({league['signup_url']})")
            await asyncio.sleep(60)  # task runs every 4 hrs


class LeagueFetcher:
    def fetch_league_data(self):
        for attempt in range(RETRY_ATTEMPTS):
            try:
                response = requests.get(API_URL, timeout=10)
                response.raise_for_status()
                return response.json()
            except requests.RequestException as e:
                logger.info(f"API request failed (attempt {attempt + 1}): {e}")
                time.sleep(RETRY_DELAY * (2 ** attempt))
        logger.error("Failed to fetch data after multiple attempts.")
        return None


    def load_previous_results(self):
        try:
            with open(PREVIOUS_RESULTS_FILE, "r") as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            return []


    def save_results(self, results):
        with open(PREVIOUS_RESULTS_FILE, "w") as file:
            json.dump(results, file, indent=4)


    def check_for_updates(self, new_data, old_data):
        old_leagues = {league["name"]: league for league in old_data}
        new_leagues = {league["name"]: league for league in new_data}

        logger.info("Open leagues")

        # gross but whatever, doesn't matter
        for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
            if DAY and DAY != day:
                continue
            if not DAY or DAY == day:
                logger.info(f'{day}s:')
            for league_name, league in new_leagues.items():
                if (league_name not in old_leagues or old_leagues[league_name]["status"] == STATUS) and league['day_of_week'] == day:
                    logger.info(f"  (Spots left: {league['open_slots']}): {league['name']} signup: ({league['signup_url']})")

    def day_of_week(self, d):
        date_obj = datetime.strptime(d, "%Y-%m-%d")
        return date_obj.strftime("%A").lower()

    def refine_league(self, league):
        league['day_of_week'] = self.day_of_week(league['start_date'])
        league['is_full'] = league['teams'] >= league['team_size']
        league['open_slots'] = league['team_size'] - league['teams']
        league['signup_url'] = f"https://users.clevelandplays.com/league/team-registration/{league['id']}/{league['sport']['id']}"
        league['play_level'] = league['play_level'].lower()   # shoudl prob iterate over all keys and make lower
        return league

    def run(self):
        new_data = self.fetch_league_data()
        if new_data is None:
            return

        data = [self.refine_league(league) for league in new_data['data']['rows']]

        data = [league for league in data if league["play_level"] == PLAY_LEVEL and league["status"] == STATUS]

        old_data = self.load_previous_results()
        self.check_for_updates(data, old_data)
        self.save_results(data)

        return data

def main():
    load_dotenv()
    bool_str = lambda x: x.lower() in ['true', '1', 't', 'y', 'yes']
    # discord_enabled = bool_str(os.environ.get("DISCORD_ENABLED"))


    f = LeagueFetcher()
    f.run()

    if discord_enabled:
        logger.info('Discord enabled')

        intents = discord.Intents.default()
        client = DiscordClient(intents=intents)

        client.task = f
        client.run(os.environ['DISCORD_TOKEN'])

if __name__ == "__main__":
    main()