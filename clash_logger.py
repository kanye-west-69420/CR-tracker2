import requests
import sqlite3
import os
import json 
from datetime import datetime

# --- CONFIGURATION ---
PLAYER_TAG_RAW = os.getenv("CR_PLAYER_TAG", "YOUR_PLAYER_TAG_HERE")
BEARER_TOKEN = os.getenv("CR_BEARER_TOKEN", "YOUR_BEARER_TOKEN_HERE")
PLAYER_TAG_URL = PLAYER_TAG_RAW.replace('#', '%23')
DB_PATH = 'clash_royale_ladder.db'

def init_database():
    """Creates the SQLite database and table with the final column order."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # MODIFIED: Added opponent tower HP columns at the end
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ladder_battles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_tag TEXT NOT NULL,
            battleTime TEXT NOT NULL,
            result TEXT,
            trophyChange INTEGER,
            currentTrophies INTEGER,
            deck TEXT,
            crowns INTEGER,
            elixirLeaked REAL,
            kingTowerHP INTEGER,
            princessTowersHP TEXT,
            opponent_tag TEXT,
            opponent_name TEXT,
            opponent_deck TEXT,
            opponent_kingTowerHP INTEGER,
            opponent_princessTowersHP TEXT,
            UNIQUE(player_tag, battleTime)
        )
    """)
    conn.commit()
    conn.close()

def format_deck(cards):
    """Sorts card names and joins them into a single string."""
    if not cards:
        return ""
    card_names = sorted([card['name'] for card in cards])
    return ' | '.join(card_names)

def fetch_and_process_battles():
    """Fetches battle data, filters for ladder matches, and extracts all specified stats."""
    api_url = f'https://proxy.royaleapi.dev/v1/players/{PLAYER_TAG_URL}/battlelog'
    headers = {'Authorization': f'Bearer {BEARER_TOKEN}'}
    print(f"[{datetime.now()}] Fetching data from API for tag {PLAYER_TAG_RAW}...")

    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        battles = response.json()

        processed_data = []
        for battle in battles:
            if battle.get('gameMode', {}).get('name') == 'Ladder':
                player_info = battle['team'][0]
                opponent_info = battle['opponent'][0] if battle.get('opponent') else {}
                
                trophy_change = player_info.get('trophyChange', 0)

                if trophy_change > 0: result = 'Win'
                elif trophy_change < 0: result = 'Loss'
                else: result = 'Draw'

                current_trophies = player_info.get('startingTrophies', 0) + trophy_change
                
                # MODIFIED: Final battle_record with all requested data in order
                battle_record = [
                    battle.get('battleTime'),
                    result,
                    trophy_change,
                    current_trophies,
                    format_deck(player_info.get('cards')),
                    player_info.get('crowns', 0),
                    player_info.get('elixirLeaked'),
                    player_info.get('kingTowerHitPoints'),
                    json.dumps(player_info.get('princessTowersHitPoints', [])),
                    opponent_info.get('tag'),
                    opponent_info.get('name'),
                    format_deck(opponent_info.get('cards')),
                    opponent_info.get('kingTowerHitPoints'),
                    json.dumps(opponent_info.get('princessTowersHitPoints', []))
                ]
                processed_data.append(battle_record)

        print(f"Found and processed {len(processed_data)} ladder battles.")
        return processed_data

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return []

def save_data_to_sqlite(data):
    """Saves the processed data to the SQLite database, avoiding duplicates."""
    if not data:
        print("No new data to save.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    new_rows_count = 0
    for row in data:
        try:
            # MODIFIED: Final INSERT statement with all 15 columns
            cursor.execute("""
                INSERT OR IGNORE INTO ladder_battles 
                (player_tag, battleTime, result, trophyChange, currentTrophies, deck, crowns, elixirLeaked, kingTowerHP, princessTowersHP, opponent_tag, opponent_name, opponent_deck, opponent_kingTowerHP, opponent_princessTowersHP)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (PLAYER_TAG_RAW, *row))
            
            new_rows_count += cursor.rowcount

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    conn.commit()
    conn.close()
    
    if new_rows_count > 0:
        print(f"Saved {new_rows_count} new rows to the database.")
    else:
        print("No unique new battles to add to the database.")

if __name__ == "__main__":
    if not all([PLAYER_TAG_RAW, BEARER_TOKEN]):
        print("Error: CR_PLAYER_TAG or CR_BEARER_TOKEN environment variables not set.")
    else:
        init_database()
        battle_data = fetch_and_process_battles()
        if battle_data:
            battle_data.reverse()
            save_data_to_sqlite(battle_data)
        print("--- Script finished ---")
