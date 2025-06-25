from django.db import connection
from typing import Any
import random
from app_logs.utils import create_SQL_log
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


##############################################
##############################################
#################### SONG ####################
##############################################
##############################################
class Song:
    def __init__(self, song_id=None, title=None, sub_title=None, description=None, artist=None, status=None, full_title=None):
        self.song_id = song_id
        self.title = title
        self.sub_title = sub_title
        self.description = description
        self.artist = artist
        self.status = status
        self.full_title = full_title
        self.verses = []
        self.genres = []
        self.links = []

        self.get_links()
        self.get_genres()
        if self.song_id:
            self.moderator_songs_with_all_message_done()


    @staticmethod
    def get_all_songs(search_txt: str = '',
                      search_everywhere: bool = False,
                      search_logic: int = 0,
                      search_genres: str = '') -> list[dict[str, Any]]:
        
        search_genres_is_null = '0'
        if not search_genres:
            search_genres = '0'
            search_genres_is_null = '1'

        search_logic_SQL = ''
        if search_logic:
            for genre in search_genres.split(','):
                search_logic_SQL += f"""
      AND EXISTS (SELECT 1 FROM l_song_genre lsg WHERE lsg.song_id = ls1.song_id AND lsg.genre_id = {genre})"""


        request = f"""
   SELECT ls1.*,
          CONCAT(ls1.title,
                 CASE
                     WHEN ls1.sub_title != '' THEN CONCAT(' - ', ls1.sub_title)
                     ELSE ''
                 END,
                 CASE
                     WHEN ls1.artist != '' THEN CONCAT(' [', ls1.artist, ']')
                     ELSE ''
                 END,
                 CASE
                     WHEN ls1.status = 1 THEN ' ✔️'
                     WHEN ls1.status = 2 THEN ' ✔️⁉️'
                     ELSE ''
                 END) AS full_title,
          CONCAT('[', GROUP_CONCAT(CONCAT(lg.`group`, '|', lg.name)), ']') AS genres
     FROM l_songs ls1
LEFT JOIN l_song_genre lsg ON lsg.song_id = ls1.song_id
LEFT JOIN l_genres lg ON lg.genre_id = lsg.genre_id
    WHERE ({search_everywhere} IS FALSE
           AND (ls1.title LIKE '%{search_txt}%'
                OR ls1.sub_title LIKE '%{search_txt}%'
                OR ls1.artist LIKE '%{search_txt}%')
            OR {search_everywhere} IS TRUE
           AND (ls1.title LIKE '%{search_txt}%'
                OR ls1.sub_title LIKE '%{search_txt}%'
                OR ls1.artist LIKE '%{search_txt}%'
                OR ls1.description LIKE '%{search_txt}%'
                OR EXISTS (SELECT 1
                             FROM l_songs ls2
                             JOIN l_verses lv ON lv.song_id = ls2.song_id
                            WHERE ls2.song_id= ls1.song_id
                              AND lv.text LIKE '%{search_txt}%'
                          )
               )
          )
      AND (lg.genre_id IN ({search_genres})
           OR {search_genres_is_null} = 1){search_logic_SQL}
 GROUP BY ls1.song_id, ls1.title, ls1.sub_title, ls1.description, ls1.artist, ls1.status,
          CONCAT(ls1.title,
                 CASE
                     WHEN ls1.sub_title != '' THEN CONCAT(' - ', ls1.sub_title)
                     ELSE ''
                 END,
                 CASE
                     WHEN ls1.artist != '' THEN CONCAT(' [', ls1.artist, ']')
                     ELSE ''
                 END,
                 CASE
                     WHEN ls1.status = 1 THEN ' ✔️'
                     WHEN ls1.status = 2 THEN ' ✔️⁉️'
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
                 'artist': row[4],
                 'status': row[5],
                 'full_title': row[6],
                 'genres': row[7]
                 } for row in rows]
    

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
                        lyrics += str(verse.num_verse) + ". "
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
    

    @classmethod
    def get_song_by_id(cls, song_id):
        with connection.cursor() as cursor:
            request = """
SELECT *, CONCAT(title,
                 CASE
                     WHEN sub_title != '' THEN CONCAT(' - ', sub_title)
                     ELSE ''
                 END,
                 CASE
                     WHEN artist != '' THEN CONCAT(' [', artist, ']')
                     ELSE ''
                 END,
                 CASE
                     WHEN status = 1 THEN ' ✔️'
                     WHEN status = 2 THEN ' ✔️⁉️'
                     ELSE ''
                 END) AS full_title
  FROM l_songs
 WHERE song_id = %s
"""
            params = [song_id]
            
            create_SQL_log(code_file, "Song.get_song_by_id", "SELECT_2", request, params)
            cursor.execute(request, params)
            row = cursor.fetchone()
        if row:
            return cls(song_id=row[0], title=row[1], sub_title=row[2], description=row[3], artist=row[4], status=row[5], full_title=row[6])
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
       artist = %s
 WHERE song_id = %s
   AND (status = 0 OR 1 = %s)
"""
                params = [self.title, self.sub_title, self.description, self.artist, self.song_id, moderator]
                
                create_SQL_log(code_file, "Song.save", "UPDATE_1", request, params)
                try:
                    cursor.execute(request, params)
                    affected_rows = cursor.rowcount
                    return affected_rows > 0
                except Exception as e:
                    return False

            else:
                request = """
INSERT INTO l_songs (title, sub_title, description, artist)
     VALUES (%s, %s, %s, %s)
"""
                params = [self.title, self.sub_title, self.description, self.artist]
                
                create_SQL_log(code_file, "Song.save", "INSERT_1", request, params)
                try:
                    cursor.execute(request, params)
                    self.song_id = cursor.lastrowid
                    return True
                except Exception as e:
                    return False


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
           @prev_group := tt.`group`
      FROM (  SELECT lg.genre_id,
                     lg.`group`,
                     lg.name
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
INSERT INTO l_songs_mod_message (song_id, message)
     VALUES (%s, %s)
"""
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
ORDER BY date DESC
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
                return "co"



######################################################
######################################################
#################### CHORUS/VERSE ####################
######################################################
######################################################
class Verse:
    def __init__(self, verse_id=None, song_id=None, num=1000, num_verse=None, chorus=0,
                 followed=0, notcontinuenumbering=1, like_chorus=0, notdisplaychorusnext=0, text="",
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
       text
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
       text = %s
 WHERE verse_id = %s
 """
                params = [self.num, self.num_verse, self.chorus, self.followed, self.notcontinuenumbering, self.text, self.verse_id]

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
    def __init__(self, genre_id=None, group=None, name=None):
        self.genre_id = genre_id
        self.group = group
        self.name = name

    @staticmethod
    def get_all_genres():
        with connection.cursor() as cursor:
            request = """
  SELECT *
    FROM l_genres
ORDER BY `group`, name
"""
            create_SQL_log(code_file, "Genre.get_all_genres", "SELECT_8", request, [])
            cursor.execute(request)
            rows = cursor.fetchall()
        return [Genre(genre_id=row[0], group=row[1], name=row[2]) for row in rows]
    

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
                cursor.execute(request, params)
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