import os
import csv
import json
import queue
import random
import aiohttp
import isodate
import datetime
import attrs

play_count: dict[int, dict[str, int]] = {}
recently_played = queue.Queue(maxsize=100)



def get_play_count(user_id: int, song_id: str) -> int:
    return play_count.get(user_id, {}).get(song_id, 0)

def increment_play_count(user_id: int, song_id: str):
    if user_id not in play_count:
        play_count[user_id] = {}
    play_count[user_id][song_id] = play_count[user_id].get(song_id, 0) + 1

@attrs.define()
class Song:
    id: str
    views: int
    duration: datetime.timedelta

    def play_count(self, user_id: int) -> int:
        return get_play_count(user_id, self.id)
    
    def total_play_count(self, *user_ids: int) -> int:
        return sum(get_play_count(user_id, self.id) for user_id in user_ids)

    def weight(self, *user_ids: int) -> int:
        return self.views // 1000 - self.total_play_count(*user_ids)
    
def load_songs():
    if os.path.exists('src/SiIvaGunner Rips - SiIvaGunner.csv'):
        with open('src/SiIvaGunner Rips - SiIvaGunner.csv', 'r') as file:
            data = csv.reader(file)
            headers = next(data)
            i_title = headers.index("Title")
            i_vidstatus = headers.index("Video Status")
            i_views = headers.index("Views")
            i_length = headers.index("Length")
            songs = []
            for r in data:
                if r[i_vidstatus] == "Public" and "announcment" not in r[i_title].lower():
                    songs.append(
                        Song(id=r[0], 
                             views=int(r[i_views]), 
                             duration=isodate.parse_duration(r[i_length]),
                             ))
    else:
        songs = []
    return songs

songs = load_songs()


async def update_rips():
    async with aiohttp.ClientSession() as session:
        rips = await session.get("https://docs.google.com/spreadsheets/d/1B7b9jEaWiqZI8Z8CzvFN1cBvLVYwjb5xzhWtrgs4anI/gviz/tq?tqx=out:csv&sheet=SiIvaGunner")
        content = await rips.text()
        with open('src/SiIvaGunner Rips - SiIvaGunner.csv', 'w') as file:
            file.write(content)
    songs.clear()
    songs.extend(load_songs())

random_picks: dict[tuple, list[Song]] = {}

def choose_random_song(*user_ids: int) -> Song:
    if user_ids not in random_picks or not random_picks[user_ids]:
        opt = []
        weights = []
        for s in songs:
            if s not in recently_played.queue:
                opt.append(s)
                weights.append(s.weight(*user_ids))
        random_picks[user_ids] = random.choices(opt, weights, k=50)
    
    song = random_picks[user_ids].pop()
    recently_played.put(song)
    return song

def save_play_counts():
    data = json.dumps(play_count)
    with open('play_count.json', 'w') as file:
        file.write(data)

def load_play_counts():
    global play_count
    if os.path.exists('play_count.json'):
        with open('play_count.json', 'r') as file:
            play_count = json.load(file)

load_play_counts()
