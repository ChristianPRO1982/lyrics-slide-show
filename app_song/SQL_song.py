from typing import Any
from django.db import connection
from app_logs.utils import create_SQL_log



code_file = "SQL_song.py"


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
        if self.song_id:
            self.moderator_songs_with_all_message_done()


    @staticmethod
    def get_all_songs():
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
ORDER BY title, sub_title
"""
        params = []

        create_SQL_log(code_file, "Song.get_all_songs", "SELECT_1", request, params)
        with connection.cursor() as cursor:
            cursor.execute(request, params)
            rows = cursor.fetchall()
        return [{'song_id': row[0], 'title': row[1], 'sub_title': row[2], 'description': row[3], 'artist': row[4], 'status': row[5], 'full_title': row[6]} for row in rows]
    

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
        self.verses = Verse.get_verses_by_song_id(self.song_id)


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
                 followed=0, notcontinuenumbering=1, like_chorus=0, notdisplaychorusnext=0, text=""):
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

    @staticmethod
    def get_verses_by_song_id(song_id):
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
                      text=row[8]) for row in rows]

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