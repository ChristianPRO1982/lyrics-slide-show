from django.conf import settings
import sqlite3
from .POO import Chorus, Verse



def get_song_lyrics(song_id: int)->str:
    conn = sqlite3.connect(f'{settings.BASE_DIR}/db.sqlite3')
    cursor = conn.cursor()

    query = f"""
SELECT chorus, num_verse, followed, text
  FROM app_main_verse
 WHERE song_id = {song_id}
    """
    
    cursor.execute(query)
    choruses_verses = cursor.fetchall()

    choruses = []
    verses = []
    start = True
    for chorus_verse in choruses_verses:
        if chorus_verse[0] == True:
            print('chorus')
            choruses.append(Chorus(chorus_verse[2], chorus_verse[3], start))
        else:
            print('verse')
            verses.append(Verse(chorus_verse[1], chorus_verse[2], chorus_verse[3]))
        start = False

    conn.close()

    return song_lyrics(choruses, verses)


def song_lyrics(choruses, verses)->str:
    chorus_str = ''
    start = -1

    for chorus in choruses:
        if start == -1:
            start = chorus.start
        chorus_str += f"<b>{chorus.text}</b>\n\n"
    
    if start:
        lyrics = chorus_str
    else:
        lyrics = ''
    
    for verse in verses:
        lyrics += f"{verse.text}\n\n"
        if not verse.followed:
            lyrics += chorus_str

    return lyrics.replace("\n", "<br>")