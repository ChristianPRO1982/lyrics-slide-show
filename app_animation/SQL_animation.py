from django.db import connection
from app_logs.utils import create_SQL_log
from app_song.SQL_song import Song



code_file = "SQL_animation.py"


###################################################
###################################################
#################### ANIMATION ####################
###################################################
###################################################
class Animation:
    def __init__(self, animation_id=None, name=None, description=None, date=None):
        self.animation_id = animation_id
        self.name = name
        self.description = description
        self.date = date
        self.songs = []
        self.all_songs()


    @staticmethod
    def get_all_animations():
        request = """
  SELECT *
    FROM l_animations
ORDER BY date, name
"""
        params = []

        create_SQL_log(code_file, "Animations.get_all_animations", "SELECT_1", request, params)
        with connection.cursor() as cursor:
            cursor.execute(request, params)
            rows = cursor.fetchall()
        return [{'animation_id': row[0], 'name': row[1], 'description': row[2], 'date': row[3]} for row in rows]
    

    @staticmethod
    def get_all_songs():
        request = """
  SELECT song_id, artist, title, sub_title
    FROM l_songs
ORDER BY artist, title, sub_title
"""
        params = []

        create_SQL_log(code_file, "Animations.get_all_songs", "SELECT_4", request, params)
        with connection.cursor() as cursor:
            cursor.execute(request, params)
            rows = cursor.fetchall()
        return [{'song_id': row[0], 'artist': row[1], 'title': row[2], 'sub_title': row[3]} for row in rows]
    

    @classmethod
    def get_animation_by_id(cls, animation_id):
        with connection.cursor() as cursor:
            request = """
SELECT *
  FROM l_animations
 WHERE animation_id = %s
"""
            params = [animation_id]
            
            create_SQL_log(code_file, "Animations.get_animation_by_id", "SELECT_2", request, params)
            cursor.execute(request, params)
            row = cursor.fetchone()
        if row:
            return cls(animation_id=row[0], name=row[1], description=row[2], date=row[3])
        return None


    def save(self):
        with connection.cursor() as cursor:
            if self.animation_id:
                request = f"""
UPDATE l_animations
   SET name = %s,
       description = %s,
       date = %s
 WHERE animation_id = %s
"""
                params = [self.name, self.description, self.date, self.animation_id]
                
                create_SQL_log(code_file, "Animations.save", "UPDATE_1", request, params)
                cursor.execute(request, params)

            else:
                request = """
INSERT INTO l_animations (name, description, date)
     VALUES (%s, %s, %s)
"""
                params = [self.name, self.description, self.date]
                
                create_SQL_log(code_file, "Animations.save", "INSERT_1", request, params)
                cursor.execute(request, params)
                self.animation_id = cursor.lastrowid


    def delete(self):
        if not self.animation_id:
            raise ValueError("L'ID de l'animation est requis pour la supprimer.")
        with connection.cursor() as cursor:
            request = """
DELETE FROM l_anmations
      WHERE animation_id = %s
"""
            params = [self.animation_id]

            create_SQL_log(code_file, "Animations.delete", "DELETE_1", request, params)
            cursor.execute(request, params)


    def all_songs(self):
        if not self.animation_id:
            raise ValueError("L'ID de l'animation est requis pour obtenir les chants.")
        with connection.cursor() as cursor:
            request = """
SELECT *
  FROM l_animation_song
 WHERE animation_id = %s
"""
            params = [self.animation_id]

            create_SQL_log(code_file, "Animations.all_songs", "SELECT_3", request, params)
            cursor.execute(request, params)
            rows = cursor.fetchall()
            self.songs = [{'animation_song_id': row[0], 'animation_id': row[1], 'song_id': row[2], 'order': row[3], 'verses': row[4]} for row in rows]
    

    def new_song_verses(self, song_id=None):
        if not self.animation_id:
            raise ValueError("L'ID de l'animation est requis pour ajouter un chant.")
        if not song_id:
            raise ValueError("L'ID du chant est requis pour ajouter un chant.")
        
        with connection.cursor() as cursor:
            request = """
SELECT verse_id
  FROM l_verses
 WHERE song_id = %s
   AND chorus = FALSE
"""
            params = [song_id]

            create_SQL_log(code_file, "Animations.new_song_verses", "SELECT_5", request, params)
            cursor.execute(request, params)
            rows = cursor.fetchall()
            verses = ','.join(str(row[0]) for row in rows)

        with connection.cursor() as cursor:
            request = """
INSERT INTO l_animation_song (animation_id, song_id, verses)
     VALUES (%s, %s, %s)
"""
            params = [self.animation_id, song_id, verses]

            create_SQL_log(code_file, "Animations.new_song", "INSERT_2", request, params)
            cursor.execute(request, params)


    def update_song_order(self, animation_song_id, order):
        with connection.cursor() as cursor:
            request = """
UPDATE l_animation_song
   SET `order` = %s
 WHERE animation_song_id = %s
"""
            params = [order, animation_song_id]

            create_SQL_log(code_file, "Animations.update_song_order", "UPDATE_2", request, params)
            cursor.execute(request, params)
    

    def get_songs_already_in(self):
        with connection.cursor() as cursor:
            request = """
SELECT song_id
  FROM l_animation_song
 WHERE animation_id = %s
    """
            params = [self.animation_id]

            create_SQL_log(code_file, "Animations.get_songs_already_in", "SELECT_6", request, params)
            cursor.execute(request, params)
            rows = cursor.fetchall()
            return [row[0] for row in rows]