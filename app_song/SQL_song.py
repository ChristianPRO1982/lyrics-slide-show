from django.db import connection
from typing import Any
import random
from app_logs.utils import create_SQL_log
from app_main.utils_SQL import build_like_pattern
from .utils import check_max_lines, check_max_characters_for_a_line


code_file = "SQL_song.py"

MUSIC_EMOJIS = [
    '🎶',  # multiple musical notes
    '🎵',  # single musical note
    '🎼',  # musical score
    '𝄞',   # G clef (Unicode symbol, pas emoji mais fonctionne visuellement)
    '𝄢',   # F clef
    # '𝄫',   # double flat
    # '𝄪',   # double sharp
    '♩',   # quarter note
    '♪',   # eighth note
    '♫',   # beamed eighth notes
    '♬',   # beamed sixteenth notes
    '𝄐',   # fermata
    '𝄑',   # fermata below
    # '𝄒',   # breath mark
    # '𝄓',   # caesura
    '𝄆',   # begin repeat
    '𝄇',   # end repeat
    '𝄋',   # up bow
    # '𝄌',   # down bow
    '𝅘𝅥',   # musical symbol quarter note
    '𝅘𝅥𝅮',   # musical symbol eighth note
    '𝅘𝅥𝅯',   # musical symbol sixteenth note
]

BAND_EMOJIS = [
    '🎸',
    '🥁',
    '🎷',
    '🎺',
    '🎻',
    '🎹',
]

ARTIST_EMOJIS = [
    '🎤',  # microphone
    '🎙️',  # microphone
    '🧑‍🎤',  # artist palette
]


##############################################
##############################################
#################### SONG ####################
##############################################
##############################################
class Song:
    def __init__(self, song_id=None, title=None, sub_title=None, description=None, status=None, licensed=None, full_title=None):
        self.song_id = song_id
        self.title = title
        self.sub_title = sub_title
        self.description = description
        self.status = status
        self.licensed = licensed
        self.full_title = full_title
        self.verses = []
        self.genres = []
        self.links = []
        self.bands = []
        self.artists = []

        self.get_links()
        self.get_genres()
        if self.song_id:
            self.moderator_songs_with_all_message_done()


    @staticmethod
    def get_all_songs(is_authenticated: bool,
        search_txt: str = '',
        search_everywhere: bool = False,
        search_logic: int = 0,
        search_genres: str = '',
        search_bands: str = '',
        search_artists: str = '',
        search_song_approved: int = 0) -> list[dict[str, Any]]:

        search_txt = build_like_pattern(search_txt, accent_insensitive=True)

        search_genres_is_null = '0'
        if not search_genres:
            search_genres = '0'
            search_genres_is_null = '1'

        search_bands_is_null = '0'
        if not search_bands:
            search_bands = '0'
            search_bands_is_null = '1'

        search_artists_is_null = '0'
        if not search_artists:
            search_artists = '0'
            search_artists_is_null = '1'

        search_logic_SQL = ''
        if search_logic:
            for genre in search_genres.split(','):
                if genre != '0':
                    search_logic_SQL += f"""
      AND EXISTS (SELECT 1 FROM l_song_genre lsg WHERE lsg.song_id = ls1.song_id AND lsg.genre_id = {genre})"""
            for band in search_bands.split(','):
                if band != '0':
                    search_logic_SQL += f"""
      AND EXISTS (SELECT 1 FROM l_song_bands lsb WHERE lsb.song_id = ls1.song_id AND lsb.band_id = {band})"""
            for artist in search_artists.split(','):
                if artist != '0':
                    search_logic_SQL += f"""
      AND EXISTS (SELECT 1 FROM l_song_artists lsa WHERE lsa.song_id = ls1.song_id AND lsa.artist_id = {artist})"""


        request = f"""
   SELECT ls1.*,
          CONCAT(ls1.title,
                 CASE
                     WHEN ls1.sub_title != '' THEN CONCAT(' - ', ls1.sub_title)
                     ELSE ''
                 END,
                 CASE
                     WHEN ls1.status = 1 THEN ' ✔️'
                     WHEN ls1.status = 2 THEN ' ✔️⁉️'
                     ELSE ''
                 END,
                 CASE
                     WHEN ls1.licensed IS TRUE THEN ' 📄'
                     ELSE ''
                 END) AS full_title,
          CONCAT('[', GROUP_CONCAT(CONCAT(lg.`group`, '|', lg.name)), ']') AS genres,
          CONCAT('[', GROUP_CONCAT(CONCAT(cb.name)), ']') AS bands,
          CONCAT('[', GROUP_CONCAT(CONCAT(ca.name)), ']') AS artists
     FROM l_songs ls1
LEFT JOIN l_song_genre lsg ON lsg.song_id = ls1.song_id
LEFT JOIN l_genres lg ON lg.genre_id = lsg.genre_id
LEFT JOIN l_song_bands lsb ON lsb.song_id = ls1.song_id
LEFT JOIN c_bands cb ON cb.band_id = lsb.band_id
LEFT JOIN l_song_artists lsa ON lsa.song_id = ls1.song_id
LEFT JOIN c_artists ca ON ca.artist_id = lsa.artist_id
    WHERE (ls1.licensed IS FALSE OR {is_authenticated} IS TRUE)
      AND ({search_everywhere} IS FALSE
           AND (ls1.title LIKE '%{search_txt}%'
                OR ls1.sub_title LIKE '%{search_txt}%')
            OR {search_everywhere} IS TRUE
           AND (ls1.title LIKE '%{search_txt}%'
                OR ls1.sub_title LIKE '%{search_txt}%'
                OR ls1.description LIKE '%{search_txt}%'
                OR EXISTS (SELECT 1
                             FROM l_songs ls2
                             JOIN l_verses lv ON lv.song_id = ls2.song_id
                            WHERE ls2.song_id = ls1.song_id
                              AND lv.text LIKE '%{search_txt}%'
                          )
               )
          )
      AND (lg.genre_id IN ({search_genres})
           OR {search_genres_is_null} = 1)
      AND (cb.band_id IN ({search_bands})
           OR {search_bands_is_null} = 1)
      AND (ca.artist_id IN ({search_artists})
           OR {search_artists_is_null} = 1){search_logic_SQL}
      AND ({search_song_approved} = 0
           OR {search_song_approved} = 1 AND ls1.status > 0
           OR {search_song_approved} = 2 AND ls1.status = 0)
 GROUP BY ls1.song_id, ls1.title, ls1.sub_title, ls1.description, ls1.status,
          CONCAT(ls1.title,
                 CASE
                     WHEN ls1.sub_title != '' THEN CONCAT(' - ', ls1.sub_title)
                     ELSE ''
                 END,
                 CASE
                     WHEN ls1.status = 1 THEN ' ✔️'
                     WHEN ls1.status = 2 THEN ' ✔️⁉️'
                     ELSE ''
                 END,
                 CASE
                     WHEN ls1.licensed IS TRUE THEN ' 📄'
                     ELSE ''
                 END)
 ORDER BY ls1.title, ls1.sub_title
"""
        params = []

        create_SQL_log(code_file, "Song.get_all_songs", "SELECT_1", request, params)
        with connection.cursor() as cursor:
            cursor.execute(request)
            rows = cursor.fetchall()
        return [{'song_id': row[0],
                 'title': row[1],
                 'sub_title': row[2],
                 'description': row[3],
                 'status': row[4],
                 'licensed': row[5],
                 'full_title': row[6],
                 'genres': row[7],
                 'bands': row[8],
                 'artists': row[9]
                 } for row in rows]
    

    @staticmethod
    def get_total_songs():
        with connection.cursor() as cursor:
            request = "SELECT COUNT(1) FROM l_songs"

            create_SQL_log(code_file, "Song.get_total_songs", "SELECT_10", request, [])
            cursor.execute(request)
            row = cursor.fetchone()
        return row[0] if row else 0
    

    def get_lyrics(self):
        choruses = []
        lyrics = ""

        # Get all choruses
        for verse in self.verses:
            if verse.chorus == 1:
                choruses.append("<b>" + verse.text.replace("\n", "<br>") + "</b>")

        start_by_chorus = True
        for verse in self.verses:
            if verse.chorus != 1:
                if verse.text and not verse.like_chorus:
                    if not verse.notcontinuenumbering:
                        lyrics += "<i>" + str(verse.num_verse) + ".</i> "
                    lyrics += verse.text.replace("\n", "<br>") + "<br><br>"
                if verse.text and verse.like_chorus:
                    lyrics += "<b>" + verse.text.replace("\n", "<br>") + "</b><br><br>"
                if not verse.followed and not verse.notdisplaychorusnext and choruses:
                    lyrics += "<br><br>".join(choruses) + "<br><br>"
            elif start_by_chorus:
                lyrics += "<br><br>".join(choruses) + "<br><br>"
            start_by_chorus = False
        
        if not lyrics:
            lyrics = "<br><br>".join(choruses)

        
        return lyrics
    

    def get_lyrics_to_display(self, display_the_chorus_once, Site):
        site = Site

        choruses = []
        choruses_printed = False
        chorus_marker = site.chorus_prefix
        verse_marker1 = site.verse_prefix1
        verse_marker2 = site.verse_prefix2
        lyrics = ""

        # Get all choruses
        for verse in self.verses:
            if verse.chorus == 1:
                choruses.append("<b><i>" + chorus_marker + "</i>" + verse.text.replace("\n", "<br>") + "</b>")
                chorus_marker = ''
        
        start_by_chorus = True
        for verse in self.verses:
            if verse.chorus != 1:
                if verse.text and not verse.like_chorus:
                    if not verse.notcontinuenumbering:
                        lyrics += f"<i>{verse_marker1}{verse.num_verse}{verse_marker2}</i>"
                    lyrics += verse.text.replace("\n", "<br>") + "<br><br>"
                if verse.text and verse.like_chorus:
                    if verse.prefix:
                        lyrics += f"<i>{verse.prefix}</i><br>"
                    lyrics += "<b>" + verse.text.replace("\n", "<br>") + "</b><br><br>"
                if not verse.followed and not verse.notdisplaychorusnext and choruses:
                    if not choruses_printed or not display_the_chorus_once:
                        lyrics += "<br><br>".join(choruses) + "<br><br>"
                        choruses_printed = True
            elif start_by_chorus:
                if not choruses_printed or not display_the_chorus_once:
                    lyrics += "<br><br>".join(choruses) + "<br><br>"
                    choruses_printed = True
            start_by_chorus = False
        
        if not lyrics:
            lyrics = "<br><br>".join(choruses)

        
        return lyrics
    

    @classmethod
    def get_song_by_id(cls, song_id, is_authenticated: bool):
        with connection.cursor() as cursor:
            request = """
SELECT *, CONCAT(title,
                 CASE
                     WHEN sub_title != '' THEN CONCAT(' - ', sub_title)
                     ELSE ''
                 END,
                 CASE
                     WHEN status = 1 THEN ' ✔️'
                     WHEN status = 2 THEN ' ✔️⁉️'
                     ELSE ''
                 END,
                 CASE
                     WHEN licensed IS TRUE THEN ' 📄'
                     ELSE ''
                 END) AS full_title
  FROM l_songs
 WHERE song_id = %s
   AND (licensed IS FALSE OR %s IS TRUE)
"""
            params = [song_id, is_authenticated]

            create_SQL_log(code_file, "Song.get_song_by_id", "SELECT_2", request, params)
            cursor.execute(request, params)
            row = cursor.fetchone()
        if row:
            return cls(
                song_id=row[0],
                title=row[1],
                sub_title=row[2],
                description=row[3],
                status=row[4],
                licensed=row[5],
                full_title=row[6])
        return None
    

    @classmethod
    def song_already_exists(cls, title, sub_title):
        with connection.cursor() as cursor:
            request = """
SELECT COUNT(1)
  FROM l_songs
 WHERE title = %s
   AND sub_title = %s
"""
            params = [title, sub_title]
            
            create_SQL_log(code_file, "Song.song_already_exists", "SELECT_7", request, params)
            cursor.execute(request, params)
            row = cursor.fetchone()
        return row[0] > 0
    

    def save(self, moderator=0):
        with connection.cursor() as cursor:
            if self.song_id:
                request = """
UPDATE l_songs
   SET title = %s,
       sub_title = %s,
       description = %s,
       licensed = %s
 WHERE song_id = %s
   AND (status = 0 OR 1 = %s)
"""
                params = [self.title, self.sub_title, self.description, self.licensed, self.song_id, moderator]

                create_SQL_log(code_file, "Song.save", "UPDATE_1", request, params)
                try:
                    cursor.execute(request, params)
                    affected_rows = cursor.rowcount
                    return affected_rows > 0
                except Exception as e:
                    return 0

            else:
                request = """
INSERT INTO l_songs (title, sub_title, description)
     VALUES (%s, %s, %s)
"""
                params = [self.title, self.sub_title, self.description]
                
                create_SQL_log(code_file, "Song.save", "INSERT_1", request, params)
                try:
                    cursor.execute(request, params)
                    self.song_id = cursor.lastrowid
                    return 0
                except Exception as e:
                    if 'Duplicate entry' in str(e):
                        return 1
                    return 2


    def delete(self):
        if not self.song_id:
            raise ValueError("L'ID du chant est requis pour le supprimer.")
        with connection.cursor() as cursor:
            request = """
DELETE FROM l_songs
      WHERE song_id = %s
"""
            params = [self.song_id]

            create_SQL_log(code_file, "Song.delete", "DELETE_1", request, params)
            cursor.execute(request, params)


    def update_status(self, status):
        with connection.cursor() as cursor:
            request = """
UPDATE l_songs
   SET status = %s
 WHERE song_id = %s
"""
            params = [status, self.song_id]
            
            create_SQL_log(code_file, "Song.update_status", "UPDATE_3", request, params)
            cursor.execute(request, params)


    def get_verses(self):
        self.verses = Verse.get_verses_by_song_id(self.song_id, self.verse_max_lines, self.verse_max_characters_for_a_line)


    def new_verse(self):
        verse = Verse(song_id=self.song_id, num=1000)
        verse.save()
        self.get_verses()

    
    def get_links(self):
        self.links = []

        with connection.cursor() as cursor:
            request = """
  SELECT link
    FROM l_song_link
   WHERE song_id = %s
ORDER BY link
"""
            params = [self.song_id]
            
            create_SQL_log(code_file, "Song.get_links", "SELECT_4", request, params)
            cursor.execute(request, params)
            rows = cursor.fetchall()

            for row in rows:
                self.links.append((row[0], row[0].split('/')[2] if '//' in row[0] else 'LINK'))


    def get_genres(self):
        self.genres = []

        with connection.cursor() as cursor:
            request = """
    SELECT tt.genre_id,
           tt.`group`,
           tt.name,
           CASE
               WHEN @prev_group IS NULL OR tt.`group` != @prev_group THEN 1
               ELSE 0
           END AS is_new_group,
           full_name,
           @prev_group := tt.`group`
      FROM (  SELECT lg.genre_id,
                     CASE WHEN REGEXP_REPLACE(lg.`group`, '^[0-9 _\-]+', '') = '' THEN lg.`group` ELSE REGEXP_REPLACE(lg.`group`, '^[0-9 _\-]+', '') END AS `group`,
                     CASE WHEN REGEXP_REPLACE(lg.name, '^[0-9 _\-]+', '') = '' THEN lg.name ELSE REGEXP_REPLACE(lg.name, '^[0-9 _\-]+', '') END AS name,
                     lg.name AS full_name
                FROM l_song_genre lsg
                JOIN l_genres lg ON lg.genre_id = lsg.genre_id
               WHERE lsg.song_id = %s
            ORDER BY lg.`group`, lg.name) AS tt
CROSS JOIN (SELECT @prev_group := NULL) vars
"""
            params = [self.song_id]

            create_SQL_log(code_file, "Song.get_genres", "SELECT_9", request, params)
            cursor.execute(request, params)
            rows = cursor.fetchall()
            for row in rows:
                self.genres.append({
                    'genre_id': row[0],
                    'group': row[1],
                    'name': row[2],
                    'is_new_group': row[3],
                    'full_name': row[4],
                    'emoji_random': random.choice(MUSIC_EMOJIS)
                })


    def clear_genres(self):
        with connection.cursor() as cursor:
            request = """
DELETE FROM l_song_genre
      WHERE song_id = %s
"""
            params = [self.song_id]

            create_SQL_log(code_file, "Song.clear_genres", "DELETE_5", request, params)
            cursor.execute(request, params)


    def add_genre(self, genre_id: int):
        with connection.cursor() as cursor:
            request = """
INSERT INTO l_song_genre (song_id, genre_id)
     VALUES (%s, %s)
"""
            params = [self.song_id, genre_id]

            create_SQL_log(code_file, "Song.add_genre", "INSERT_6", request, params)
            try:
                cursor.execute(request, params)
                return ''
            except Exception as e:
                return '[ERR32]'


    def moderator_new_message(self, message: str)->int:
        with connection.cursor() as cursor:
            request = """
INSERT INTO l_songs_mod_message (song_id, message, date)
     VALUES (%s, %s, CONVERT_TZ(NOW(), '+00:00', 'Europe/Paris'))
"""
# for debug: a version of MySQL that does not support CONVERT_TZ()
#             request = """
# INSERT INTO l_songs_mod_message (song_id, message, date)
#      VALUES (%s, %s, NOW())
# """
            params = [self.song_id, message]
            
            try:
                create_SQL_log(code_file, "Song.moderator_new_message", "INSERT_3", request, params)
                cursor.execute(request, params)
                
                request = """
UPDATE l_songs
   SET status = 2
 WHERE song_id = %s
"""
                params = [self.song_id]

                try:
                    create_SQL_log(code_file, "Song.moderator_new_message", "UPDATE_4", request, params)
                    cursor.execute(request, params)
                    return 0
                except Exception as e:
                    return 2
            except Exception as e:
                return 1
            

    def get_moderator_new_messages(self):
        with connection.cursor() as cursor:
            request = """
  SELECT message_id, message, date
    FROM l_songs_mod_message
   WHERE song_id = %s
     AND status <> 1
ORDER BY date ASC
"""
            params = [self.song_id]
            
            create_SQL_log(code_file, "Song.get_moderator_new_messages", "SELECT_5", request, params)
            cursor.execute(request, params)
            mod_new_messages = [
                {'id': row[0], 'message': row[1], 'date': row[2]}
                for row in cursor.fetchall()
            ]
            return mod_new_messages


    def get_moderator_old_messages(self):
        with connection.cursor() as cursor:
            request = """
  SELECT message_id, message, date
    FROM l_songs_mod_message
   WHERE song_id = %s
     AND status = 1
ORDER BY date DESC
"""
            params = [self.song_id]
            
            create_SQL_log(code_file, "Song.get_moderator_old_messages", "SELECT_6", request, params)
            cursor.execute(request, params)
            mod_old_messages = [
                {'id': row[0], 'message': row[1], 'date': row[2]}
                for row in cursor.fetchall()
            ]
            return mod_old_messages
        

    def moderator_message_done(self, message_id: int):
        with connection.cursor() as cursor:
            request = """
UPDATE l_songs_mod_message
   SET status = 1
 WHERE message_id = %s
"""
            params = [message_id]
            create_SQL_log(code_file, "Song.moderator_message_done", "UPDATE_5", request, params)
            cursor.execute(request, params)

        self.moderator_songs_with_all_message_done()


    def moderator_songs_with_all_message_done(self):
        with connection.cursor() as cursor:
            request = """
UPDATE l_songs ls
   SET status = 1
 WHERE ls.song_id = %s
   AND ls.status = 2
   AND 0 IN (SELECT COUNT(1)
               FROM l_songs_mod_message lsmm
              WHERE lsmm.song_id = %s
                AND lsmm.status = 0)
"""
            params = [self.song_id, self.song_id]
            create_SQL_log(code_file, "Song.moderator_songs_with_all_message_done", "UPDATE_6", request, params)
            cursor.execute(request, params)

            request = """
UPDATE l_songs ls
   SET status = 2
 WHERE ls.song_id = %s
   AND ls.status = 1
   AND 0 < (SELECT COUNT(1)
              FROM l_songs_mod_message lsmm
             WHERE lsmm.song_id = %s
               AND lsmm.status = 0)
"""
            params = [self.song_id, self.song_id]
            create_SQL_log(code_file, "Song.moderator_songs_with_all_message_done", "UPDATE_7", request, params)
            cursor.execute(request, params)


    def add_link(self, link: str):
        with connection.cursor() as cursor:
            request = """
INSERT INTO l_song_link (song_id, link)
     VALUES (%s, %s)
"""
            params = [self.song_id, link]
            
            create_SQL_log(code_file, "Song.add_link", "INSERT_4", request, params)
            try:
                cursor.execute(request, params)
                return ''
            except Exception as e:
                return e
            

    def delete_link(self, link: str):
        with connection.cursor() as cursor:
            request = """
DELETE FROM l_song_link
      WHERE song_id = %s
        AND link = %s
"""
            params = [self.song_id, link]
            create_SQL_log(code_file, "Song.delete_link", "DELETE_3", request, params)
            try:
                cursor.execute(request, params)
                return ''
            except Exception as e:
                return '[ERR21]'


    def update_link(self, old_link: str, new_link: str):
        with connection.cursor() as cursor:
            request = """
UPDATE l_song_link
   SET link = %s
 WHERE song_id = %s
   AND link = %s
"""
            params = [new_link, self.song_id, old_link]
            create_SQL_log(code_file, "Song.upadate_link", "UPDATE_8", request, params)
            try:
                cursor.execute(request, params)
                return ''
            except Exception as e:
                return e
            

    @staticmethod
    def get_verse_prefixes():
        with connection.cursor() as cursor:
            request = """
SELECT prefix_id, prefix, comment
  FROM l_verse_prefixes
ORDER BY prefix
"""
            params = []

            create_SQL_log(code_file, "Song.get_verse_prefixes", "SELECT_11", request, params)
            cursor.execute(request, params)
            rows = cursor.fetchall()
        return [{
            'prefix_id': row[0],
            'prefix': row[1],
            'comment': row[2]
            } for row in rows]
    

    @staticmethod
    def add_prefix(prefix: str, comment: str):
        with connection.cursor() as cursor:
            request = """
INSERT INTO l_verse_prefixes (prefix, comment)
     VALUES (%s, %s)
"""
            params = [prefix, comment]

            create_SQL_log(code_file, "Song.add_prefix", "INSERT_7", request, params)
            try:
                cursor.execute(request, params)
                return ''
            except Exception as e:
                if 'Duplicate entry' in str(e):
                    return '[ERR36]'
                return '[ERR37]'
            

    @staticmethod
    def delete_prefix(prefix_id: int):
        with connection.cursor() as cursor:
            request = """
DELETE FROM l_verse_prefixes
      WHERE prefix_id = %s
"""
            params = [prefix_id]

            create_SQL_log(code_file, "Song.delete_prefix", "DELETE_6", request, params)
            try:
                cursor.execute(request, params)
                return ''
            except Exception as e:
                return '[ERR38]'
            

    @staticmethod
    def get_all_bands_and_artists():
        bands = []
        artists = []

        with connection.cursor() as cursor:
            request = """
   SELECT "band" type, cb.band_id id, cb.name
     FROM c_bands cb
UNION ALL
   SELECT "artist" type, ca.artist_id id, ca.name
     FROM c_artists ca
 ORDER BY name
"""
            params = []

            create_SQL_log(code_file, "Song.get_all_bands_and_artists", "SELECT_12", request, params)
            cursor.execute(request, params)
            rows = cursor.fetchall()
            for row in rows:
                if row[0] == 'band':
                    bands.append({'band_id': row[1], 'name': row[2]})
                else:
                    artists.append({'artist_id': row[1], 'name': row[2]})

        return bands, artists
            

    def get_bands_and_artists(self):
        self.bands = []
        self.artists = []

        with connection.cursor() as cursor:
            request = """
   SELECT "band" type, cb.band_id id, cb.name, lsb.song_id
     FROM c_bands cb
LEFT JOIN l_song_bands lsb ON lsb.band_id = cb.band_id
                          AND lsb.song_id = %s
UNION ALL
   SELECT "artist" type, ca.artist_id id, ca.name, lsa.song_id
     FROM c_artists ca
LEFT JOIN l_song_artists lsa ON lsa.artist_id = ca.artist_id
                           AND lsa.song_id = %s
 ORDER BY name
"""
            params = [self.song_id, self.song_id]

            create_SQL_log(code_file, "Song.get_bands_and_artists", "SELECT_12", request, params)
            cursor.execute(request, params)
            rows = cursor.fetchall()
            for row in rows:
                if row[0] == 'band':
                    self.bands.append({
                        'band_id': row[1],
                        'name': row[2],
                        'song_id': row[3],
                        'emoji_random': random.choice(BAND_EMOJIS)
                    })
                else:
                    self.artists.append({
                        'artist_id': row[1],
                        'name': row[2],
                        'song_id': row[3],
                        'emoji_random': random.choice(ARTIST_EMOJIS)
                    })


    def clear_bands(self):
        with connection.cursor() as cursor:
            request = """
DELETE FROM l_song_bands
      WHERE song_id = %s
"""
            params = [self.song_id]

            create_SQL_log(code_file, "Song.clear_bands", "DELETE_8", request, params)
            try:
                cursor.execute(request, params)
                return ''
            except Exception as e:
                return '[ERR] DELETE_8'
            

    def add_band(self, band_id: int):
        with connection.cursor() as cursor:
            request = """
INSERT INTO l_song_bands (song_id, band_id)
     VALUES (%s, %s)
"""
            params = [self.song_id, band_id]

            create_SQL_log(code_file, "Song.add_band", "INSERT_8", request, params)
            try:
                cursor.execute(request, params)
                return ''
            except Exception as e:
                return '[ERR48]'
            

    def clear_artists(self):
        with connection.cursor() as cursor:
            request = """
DELETE FROM l_song_artists
      WHERE song_id = %s
"""
            params = [self.song_id]

            create_SQL_log(code_file, "Song.clear_artists", "DELETE_9", request, params)
            try:
                cursor.execute(request, params)
                return ''
            except Exception as e:
                return '[ERR] DELETE_9'
            

    def add_artist(self, artist_id: int):
        with connection.cursor() as cursor:
            request = """
INSERT INTO l_song_artists (song_id, artist_id)
     VALUES (%s, %s)
"""
            params = [self.song_id, artist_id]

            create_SQL_log(code_file, "Song.add_artist", "INSERT_9", request, params)
            try:
                cursor.execute(request, params)
                return ''
            except Exception as e:
                return '[ERR49]'


######################################################
######################################################
#################### CHORUS/VERSE ####################
######################################################
######################################################
class Verse:
    def __init__(self, verse_id=None, song_id=None, num=1000, num_verse=None, chorus=0,
                 followed=0, notcontinuenumbering=1, like_chorus=0, notdisplaychorusnext=0, text="", prefix="",
                 max_lines=False, max_characters_for_a_line=False):
        self.verse_id = verse_id
        self.song_id = song_id
        self.num = num
        self.num_verse = num_verse
        self.chorus = chorus
        self.followed = followed
        self.notcontinuenumbering = notcontinuenumbering
        self.like_chorus = like_chorus
        self.notdisplaychorusnext = notdisplaychorusnext
        self.text = text
        self.prefix = prefix
        self.max_lines = max_lines
        self.max_characters_for_a_line = max_characters_for_a_line

    @staticmethod
    def get_verses_by_song_id(song_id, max_lines, max_characters_for_a_line):
        with connection.cursor() as cursor:
            request = """
SELECT verse_id,
       num,
       num_verse,
       CASE WHEN chorus > 1 THEN 0 ELSE chorus END AS chorus,
       followed,
       notcontinuenumbering,
       CASE WHEN chorus > 1 THEN 1 ELSE 0 END AS like_chorus,
       CASE WHEN chorus = 3 THEN 1 ELSE 0 END AS notdisplaychorusnext,
       text,
       prefix
    FROM l_verses
   WHERE song_id = %s
ORDER BY num
"""
            params = [song_id]

            create_SQL_log(code_file, "Verse.get_verses_by_song_id", "SELECT_3", request, params)
            cursor.execute(request, params)
            rows = cursor.fetchall()
            
        return [Verse(verse_id=row[0],
                      song_id=song_id,
                      num=row[1],
                      num_verse=row[2],
                      chorus=row[3],
                      followed=row[4],
                      notcontinuenumbering=row[5],
                      like_chorus=row[6],
                      notdisplaychorusnext=row[7],
                      text=row[8],
                      prefix=row[9],
                      max_lines=check_max_lines(row[8], max_lines),
                      max_characters_for_a_line=check_max_characters_for_a_line(row[8], max_characters_for_a_line)) for row in rows]

    def save(self):
        if not self.num:
            self.num = 1000

        if self.chorus == 0 and self.like_chorus == 1 and self.notdisplaychorusnext == 0: self.chorus = 2
        if self.chorus == 0 and self.like_chorus == 1 and self.notdisplaychorusnext == 1: self.chorus = 3
            
        with connection.cursor() as cursor:
            if self.verse_id:
                request = """
UPDATE l_verses
   SET num = %s,
       num_verse = %s,
       chorus = %s,
       followed = %s,
       notcontinuenumbering = %s,
       text = %s,
       prefix = %s
 WHERE verse_id = %s
 """
                params = [
                    self.num,
                    self.num_verse,
                    self.chorus,
                    self.followed,
                    self.notcontinuenumbering,
                    self.text,
                    self.prefix,
                    self.verse_id
                ]

                create_SQL_log(code_file, "Verse.save", "UPDATE_2", request, params)
                cursor.execute(request, params)

            else:
                request = """
INSERT INTO l_verses (song_id)
     VALUES (%s)
"""
                params = [self.song_id]

                create_SQL_log(code_file, "Verse.save", "INSERT_2", request, params)
                cursor.execute(request, params)
                self.verse_id = cursor.lastrowid

    def delete(self):
        """Supprime le couplet/refrain."""
        if not self.verse_id:
            raise ValueError("L'ID du couplet est requis pour le supprimer.")
        with connection.cursor() as cursor:
            request = """
DELETE FROM l_verses
        WHERE verse_id = %s
"""
            params = [self.verse_id]
            
            create_SQL_log(code_file, "Verse.delete", "DELETE_2", request, params)
            cursor.execute(request, params)



###############################################
###############################################
#################### GENRE ####################
###############################################
###############################################
class Genre:
    def __init__(self, genre_id=None, group=None, name=None, full_group=None, full_name=None):
        self.genre_id = genre_id
        self.group = group
        self.name = name
        self.full_group = full_group
        self.full_name = full_name

    @staticmethod
    def get_all_genres():
        with connection.cursor() as cursor:
            request = """
  SELECT genre_id,
         CASE WHEN cleaned_group = '' THEN full_group ELSE cleaned_group END AS `group`,
         CASE WHEN cleaned_name = '' THEN full_name ELSE cleaned_name END AS name,
         full_group,
         full_name
    FROM (SELECT genre_id,
               REGEXP_REPLACE(`group`, '^[0-9 _\\-]+', '') AS cleaned_group,
               REGEXP_REPLACE(name, '^[0-9 _\\-]+', '') AS cleaned_name,
               `group` AS full_group,
               name AS full_name
          FROM l_genres) AS sub
ORDER BY full_group, full_name
"""
            create_SQL_log(code_file, "Genre.get_all_genres", "SELECT_8", request, [])
            cursor.execute(request)
            rows = cursor.fetchall()
        return [Genre(
                genre_id=row[0],
                group=row[1],
                name=row[2],
                full_group=row[3],
                full_name=row[4]
            ) for row in rows]
    

    def save(self):
        with connection.cursor() as cursor:
            if self.genre_id:
                request = """
UPDATE l_genres
   SET `group` = %s,
       name = %s
 WHERE genre_id = %s
"""
                params = [self.group, self.name, self.genre_id]

                create_SQL_log(code_file, "Genre.save", "UPDATE_9", request, params)
                try:
                    cursor.execute(request, params)
                    return ''
                except Exception as e:
                    if 'Duplicate entry' in str(e):
                        return '[ERR33]'
                    return '[ERR39]'
            else:
                request = """
INSERT INTO l_genres (`group`, name)
     VALUES (%s, %s)
"""
                params = [self.group, self.name]

                create_SQL_log(code_file, "Genre.save", "INSERT_5", request, params)
                try:
                    cursor.execute(request, params)
                    self.genre_id = cursor.lastrowid
                    return ''
                except Exception as e:
                    if 'Duplicate entry' in str(e):
                        return '[ERR33]'
                    return '[ERR34]'


    def delete(self):
        if not self.genre_id:
            raise ValueError("L'ID du genre est requis pour le supprimer.")
        with connection.cursor() as cursor:
            request = """
DELETE FROM l_genres
      WHERE genre_id = %s
"""
            params = [self.genre_id]

            create_SQL_log(code_file, "Genre.delete", "DELETE_4", request, params)
            cursor.execute(request, params)


    @staticmethod
    def get_genre_id_by_name(genre_str):
        with connection.cursor() as cursor:
            request = """
SELECT genre_id
  FROM l_genres
 WHERE name = %s
"""
            params = [genre_str]

            create_SQL_log(code_file, "Genre.get_genre_id_by_name", "SELECT_13", request, params)
            cursor.execute(request, params)
            row = cursor.fetchone()

        if row:
            return row[0]
        return None
    

    @staticmethod
    def get_band_id_by_name(band_str):
        with connection.cursor() as cursor:
            request = """
SELECT band_id
  FROM c_bands
 WHERE name = %s
"""
            params = [band_str]

            create_SQL_log(code_file, "Genre.get_band_id_by_name", "SELECT_14", request, params)
            cursor.execute(request, params)
            row = cursor.fetchone()

        if row:
            return row[0]
        return None


    @staticmethod
    def get_artist_id_by_name(artist_str):
        with connection.cursor() as cursor:
            request = """
SELECT artist_id
  FROM c_artists
 WHERE name = %s
"""
            params = [artist_str]

            create_SQL_log(code_file, "Genre.get_artist_id_by_name", "SELECT_15", request, params)
            cursor.execute(request, params)
            row = cursor.fetchone()

        if row:
            return row[0]
        return None