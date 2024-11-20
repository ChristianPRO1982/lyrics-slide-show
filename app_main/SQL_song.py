from django.db import connection
import django.utils.html
import os



SQL_REQUEST = os.environ
code_file = """
SQL_song.py"""


##############################################
##############################################
#################### SONG ####################
##############################################
##############################################
class Song:
    def __init__(self, song_id=None, title=None, sub_title=None, description=None, artist=None):
        self.song_id = song_id
        self.title = title
        self.sub_title = sub_title
        self.description = description
        self.artist = artist
        self.verses = []


    @staticmethod
    def get_all_songs():
        request = """
  SELECT *
    FROM l_songs
ORDER BY title, sub_title
"""

        if SQL_REQUEST: print(code_file, ": SELECT_1", request)
        with connection.cursor() as cursor:
            cursor.execute(request)
            rows = cursor.fetchall()
        return [{'id': row[0], 'title': row[1], 'sub_title': row[2], 'description': row[3], 'artist': row[4]} for row in rows]
    

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
            request = f"""
SELECT *
  FROM l_songs
 WHERE song_id = {song_id}
"""
            
            if SQL_REQUEST: print(code_file, ": SELECT_2", request)
            cursor.execute(request)
            row = cursor.fetchone()
        if row:
            return cls(song_id=row[0], title=row[1], sub_title=row[2], description=row[3], artist=row[4])
        return None

    def save(self):
        with connection.cursor() as cursor:
            if self.song_id:
                request = f"""
UPDATE l_songs
   SET title = "{self.title}",
       sub_title = "{self.sub_title}",
       description = "{self.description}",
       artist = "{self.artist}"
 WHERE song_id = {self.song_id}"""
                
                if SQL_REQUEST: print(code_file, ": UPDATE_1", request)
                cursor.execute(request)

            else:
                request = f"""
INSERT INTO l_songs (title, sub_title, description, artist)
     VALUES ("{self.title}", "{self.sub_title}", "{self.description}", "{self.artist}")"""
                
                if SQL_REQUEST: print(code_file, ": INSERT_1", request)
                cursor.execute(request)
                self.song_id = cursor.lastrowid


    def delete(self):
        if not self.song_id:
            raise ValueError("L'ID du chant est requis pour le supprimer.")
        with connection.cursor() as cursor:
            request = f"""
DELETE FROM l_songs
      WHERE song_id = {self.song_id}"""

            if SQL_REQUEST: print(code_file, ": DELETE_1", request)
            cursor.execute(request)


    def get_verses(self):
        self.verses = Verse.get_verses_by_song_id(self.song_id)


    def new_verse(self):
        verse = Verse(song_id=self.song_id)
        verse.save()
        self.get_verses()



######################################################
######################################################
#################### CHORUS/VERSE ####################
######################################################
######################################################
class Verse:
    def __init__(self, verse_id=None, song_id=None, num=None, num_verse=None, chorus=False, followed=False, text=""):
        self.verse_id = verse_id
        self.song_id = song_id
        self.num = num
        self.num_verse = num_verse
        self.chorus = chorus
        self.followed = followed
        self.text = text

    @staticmethod
    def get_verses_by_song_id(song_id):
        with connection.cursor() as cursor:
            request = f"""
SELECT verse_id,
       num,
       num_verse,
       chorus,
       followed,
       text
    FROM l_verses
   WHERE song_id = {song_id}
ORDER BY num
"""

            if SQL_REQUEST: print(code_file, ": SELECT_3", request)
            cursor.execute(request)
            rows = cursor.fetchall()
        return [Verse(verse_id=row[0], song_id=song_id, num=row[1], num_verse=row[2], chorus=row[3], followed=row[4], text=row[5]) for row in rows]

    def save(self):
        with connection.cursor() as cursor:
            if self.verse_id:
                request = f"""
UPDATE l_verses
   SET num = {self.num},
       num_verse = {self.num_verse},
       chorus = {self.chorus},
       followed = {self.followed},
       text = "{self.text}"
 WHERE verse_id = {self.verse_id}
 """

                if SQL_REQUEST: print(code_file, ": UPDATE_2", request)
                cursor.execute(request)

            else:
                request = f"""
INSERT INTO l_verses (song_id)
     VALUES ({self.song_id})
"""

                if SQL_REQUEST: print(code_file, ": INSERT_2", request)
                cursor.execute(request)
                self.verse_id = cursor.lastrowid

    def delete(self):
        """Supprime le couplet/refrain."""
        if not self.verse_id:
            raise ValueError("L'ID du couplet est requis pour le supprimer.")
        with connection.cursor() as cursor:
            request = f"""
DELETE FROM l_verses
        WHERE verse_id = {self.verse_id}
"""
            
            if SQL_REQUEST: print(code_file, ": DELETE_2", request)
            cursor.execute(request)
