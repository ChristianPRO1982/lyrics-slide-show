from django.db import connection
from app_logs.utils import create_log, create_SQL_log
import os



code_file = """
SQL_animation.py"""


##############################################
##############################################
#################### SONG ####################
##############################################
##############################################
class Animation:
    def __init__(self, animation_id=None, name=None, description=None, date=None):
        self.animation_id = animation_id
        self.name = name
        self.description = description
        self.date = date
        self.songs = []


    @staticmethod
    def get_all_animations():
        request = """
  SELECT *
    FROM l_animations
ORDER BY date DESC, name
"""
        params = []

        create_SQL_log(code_file, "Animation.get_all_animations", "SELECT_1", request, params)
        with connection.cursor() as cursor:
            cursor.execute(request, params)
            rows = cursor.fetchall()
        return [{'id': row[0], 'name': row[1], 'sub_name': row[2], 'description': row[3], 'date': row[4]} for row in rows]
    

    def get_lyrics(self):
        choruses = []
        lyrics = ""

        # Get all choruses
        for verse in self.songs:
            if verse.chorus:
                choruses.append("<b>" + verse.text.replace("\n", "<br>") + "</b>")

        start_by_chorus = True
        for verse in self.songs:
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
    def get_song_by_id(cls, animation_id):
        with connection.cursor() as cursor:
            request = """
SELECT *
  FROM l_songs
 WHERE animation_id = %s
"""
            params = [animation_id]
            
            create_SQL_log(code_file, "Animation.get_song_by_id", "SELECT_2", request, params)
            cursor.execute(request, params)
            row = cursor.fetchone()
        if row:
            return cls(animation_id=row[0], name=row[1], sub_name=row[2], description=row[3], date=row[4])
        return None

    def save(self):
        with connection.cursor() as cursor:
            if self.animation_id:
                request = f"""
UPDATE l_songs
   SET name = %s,
       sub_name = %s,
       description = %s,
       date = %s
 WHERE animation_id = %s
"""
                params = [self.name, self.sub_name, self.description, self.date, self.animation_id]
                
                create_SQL_log(code_file, "Animation.save", "UPDATE_1", request, params)
                cursor.execute(request, params)

            else:
                request = """
INSERT INTO l_songs (name, sub_name, description, date)
     VALUES (%s, %s, %s, %s)
"""
                params = [self.name, self.sub_name, self.description, self.date]
                
                create_SQL_log(code_file, "Animation.save", "INSERT_1", request, params)
                cursor.execute(request, params)
                self.animation_id = cursor.lastrowid


    def delete(self):
        if not self.animation_id:
            raise ValueError("L'ID du chant est requis pour le supprimer.")
        with connection.cursor() as cursor:
            request = """
DELETE FROM l_songs
      WHERE animation_id = %s
"""
            params = [self.animation_id]

            create_SQL_log(code_file, "Animation.delete", "DELETE_1", request, params)
            cursor.execute(request, params)


    def get_songs(self):
        self.songs = Verse.get_songs_by_animation_id(self.animation_id)


    def new_verse(self):
        verse = Verse(animation_id=self.animation_id)
        verse.save()
        self.get_songs()



######################################################
######################################################
#################### CHORUS/VERSE ####################
######################################################
######################################################
class Verse:
    def __init__(self, verse_id=None, animation_id=None, num=None, num_verse=None, chorus=False, followed=False, text=""):
        self.verse_id = verse_id
        self.animation_id = animation_id
        self.num = num
        self.num_verse = num_verse
        self.chorus = chorus
        self.followed = followed
        self.text = text

    @staticmethod
    def get_songs_by_animation_id(animation_id):
        with connection.cursor() as cursor:
            request = """
SELECT verse_id,
       num,
       num_verse,
       chorus,
       followed,
       text
    FROM l_songs
   WHERE animation_id = %s
ORDER BY num
"""
            params = [animation_id]

            create_SQL_log(code_file, "Verse.get_songs_by_animation_id", "SELECT_3", request, params)
            cursor.execute(request, params)
            rows = cursor.fetchall()
        return [Verse(verse_id=row[0], animation_id=animation_id, num=row[1], num_verse=row[2], chorus=row[3], followed=row[4], text=row[5]) for row in rows]

    def save(self):
        with connection.cursor() as cursor:
            if self.verse_id:
                request = """
UPDATE l_songs
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
INSERT INTO l_songs (animation_id)
     VALUES (%s)
"""
                params = [self.animation_id]

                create_SQL_log(code_file, "Verse.save", "INSERT_2", request, params)
                cursor.execute(request, params)
                self.verse_id = cursor.lastrowid

    def delete(self):
        """Supprime le couplet/refrain."""
        if not self.verse_id:
            raise ValueError("L'ID du couplet est requis pour le supprimer.")
        with connection.cursor() as cursor:
            request = """
DELETE FROM l_songs
        WHERE verse_id = %s
"""
            params = [self.verse_id]
            
            create_SQL_log(code_file, "Verse.delete", "DELETE_2", request, params)
            cursor.execute(request, params)
