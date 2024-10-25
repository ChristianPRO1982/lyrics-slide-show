from django.conf import settings
import sqlite3
from .POO import Chorus, Verse



def get_song_lyrics(song_id: int)->str:
    conn = sqlite3.connect(f'{settings.BASE_DIR}/db.sqlite3')
    cursor = conn.cursor()

    query = f"""
SELECT 'chorus' type, num_verse, followed, text
  FROM app_main_verse
 WHERE song_id = {song_id}
   AND chorus = True

 UNION ALL

SELECT 'verse' type, num_verse, followed, text
  FROM app_main_verse
 WHERE song_id = {song_id}
   AND chorus = False
    """
    
    cursor.execute(query)
    verses = cursor.fetchall()

    chorus = []
    verses = []
    for verse in verses:
        if verse[0] == 'chorus':
            chorus.append(Chorus(verse[2], verse[3]))
        else:
            verses.append(Verse(verse[1], verse[2], verse[3]))

    conn.close()
    return "coucou"