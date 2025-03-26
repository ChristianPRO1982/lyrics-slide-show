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
    def __init__(self, song_id=None, title=None, sub_title=None, description=None, artist=None, full_title=None):
        self.song_id = song_id
        self.title = title
        self.sub_title = sub_title
        self.description = description
        self.artist = artist
        self.full_title = full_title
        self.verses = []


    @staticmethod
    def get_all_songs():
        request = """
  SELECT *, CONCAT(
                   CASE
                       WHEN artist != '' THEN CONCAT('[', artist, '] - ', title)
                       ELSE title
                   END,
                   CASE
                       WHEN sub_title != '' THEN CONCAT(' - ', sub_title)
                       ELSE ''
                   END) AS full_title
    FROM l_songs
ORDER BY artist, title, sub_title
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
            if verse.chorus:
                choruses.append("<b>" + verse.text.replace("\n", "<br>") + "</b>")

        start_by_chorus = True
        for verse in self.verses:
            if not verse.chorus:
                if verse.text:
                    lyrics += str(verse.num_verse) + ". " + verse.text.replace("\n", "<br>") + "<br><br>"
                if not verse.followed and choruses:
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
SELECT *, CONCAT(
                 CASE 
                     WHEN artist != '' THEN CONCAT('[', artist, '] - ', title)
                     ELSE title
                 END,
                 CASE 
                     WHEN sub_title != '' THEN CONCAT(' - ', sub_title)
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
            return cls(song_id=row[0], title=row[1], sub_title=row[2], description=row[3], artist=row[4], full_title=row[5])
        return None

    def save(self):
        with connection.cursor() as cursor:
            if self.song_id:
                request = f"""
UPDATE l_songs
   SET title = %s,
       sub_title = %s,
       description = %s,
       artist = %s
 WHERE song_id = %s
"""
                params = [self.title, self.sub_title, self.description, self.artist, self.song_id]
                
                create_SQL_log(code_file, "Song.save", "UPDATE_1", request, params)
                cursor.execute(request, params)

            else:
                request = """
INSERT INTO l_songs (title, sub_title, description, artist)
     VALUES (%s, %s, %s, %s)
"""
                params = [self.title, self.sub_title, self.description, self.artist]
                
                create_SQL_log(code_file, "Song.save", "INSERT_1", request, params)
                cursor.execute(request, params)
                self.song_id = cursor.lastrowid


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


    def get_verses(self):
        self.verses = Verse.get_verses_by_song_id(self.song_id)


    def new_verse(self):
        verse = Verse(song_id=self.song_id, num=1000)
        verse.save()
        self.get_verses()



######################################################
######################################################
#################### CHORUS/VERSE ####################
######################################################
######################################################
class Verse:
    def __init__(self, verse_id=None, song_id=None, num=1000, num_verse=None, chorus=False, followed=False, like_chorus=False, text=""):
        self.verse_id = verse_id
        self.song_id = song_id
        self.num = num
        self.num_verse = num_verse
        self.chorus = chorus
        self.followed = followed
        self.like_chorus = like_chorus
        self.text = text

    @staticmethod
    def get_verses_by_song_id(song_id):
        with connection.cursor() as cursor:
            request = """
SELECT verse_id,
       num,
       num_verse,
       CASE WHEN chorus = 2 THEN 0 ELSE chorus END AS chorus,
       followed,
       CASE WHEN chorus = 2 THEN 1 ELSE 0 END AS like_chorus,
       text
    FROM l_verses
   WHERE song_id = %s
ORDER BY num
"""
            params = [song_id]

            create_SQL_log(code_file, "Verse.get_verses_by_song_id", "SELECT_3", request, params)
            cursor.execute(request, params)
            rows = cursor.fetchall()
        return [Verse(verse_id=row[0], song_id=song_id, num=row[1], num_verse=row[2], chorus=row[3], followed=row[4], like_chorus=row[5], text=row[6]) for row in rows]

    def save(self):
        if not self.num:
            self.num = 1000
        
        if self.chorus == 0 and self.like_chorus == 1:
            self.chorus = 2
            
        with connection.cursor() as cursor:
            if self.verse_id:
                request = """
UPDATE l_verses
   SET num = %s,
       num_verse = %s,
       chorus = %s,
       followed = %s,
       text = %s
 WHERE verse_id = %s
 """
                params = [self.num, self.num_verse, self.chorus, self.followed, self.text, self.verse_id]

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
