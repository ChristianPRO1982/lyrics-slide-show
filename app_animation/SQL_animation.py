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
        self.verses = []
        self.all_verses()


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
        if self.animation_id:
            with connection.cursor() as cursor:
                request = """
  SELECT las.*, ROUND(las.num / 2, 0) as numD2,
         CONCAT(
                CASE
                    WHEN s.artist != '' THEN CONCAT('[', s.artist, '] - ', s.title)
                    ELSE title
                END,
                CASE
                    WHEN s.sub_title != '' THEN CONCAT(' - ', s.sub_title)
                    ELSE ''
                END) AS full_title
    FROM l_animation_song las
    JOIN l_songs s ON las.song_id = s.song_id
   WHERE las.animation_id = %s
ORDER BY las.num
"""
                params = [self.animation_id]

                create_SQL_log(code_file, "Animations.all_songs", "SELECT_3", request, params)
                cursor.execute(request, params)
                rows = cursor.fetchall()
                self.songs = [{
                        'animation_song_id': row[0],
                        'animation_id': row[1],
                        'song_id': row[2],
                        'num': row[3],
                        'numD2': row[4],
                        'full_title': row[5],
                    } for row in rows]


    def all_verses(self):
        if self.animation_id:
            with connection.cursor() as cursor:
                request = """
  SELECT lasv.*, lv.num_verse, lv.text
    FROM l_animation_song_verse lasv
    JOIN l_animation_song las ON las.animation_song_id = lasv.animation_song_id
    JOIN l_verses lv ON lv.verse_id = lasv.verse_id
   WHERE lv.chorus = FALSE
     AND las.animation_id = %s
ORDER BY lv.num
"""
                params = [self.animation_id]

                create_SQL_log(code_file, "Animations.all_verses", "SELECT_4", request, params)
                cursor.execute(request, params)
                rows = cursor.fetchall()
                self.verses = [{
                        'animation_song_id': row[0],
                        'verse_id': row[1],
                        'selected': row[2],
                        'num_verse': row[3],
                        'text': row[4],
                    } for row in rows]
    

    def new_song_verses(self, song_id=None):
        if not self.animation_id:
            raise ValueError("L'ID de l'animation est requis pour ajouter un chant.")
        if not song_id:
            raise ValueError("L'ID du chant est requis pour ajouter un chant.")

        with connection.cursor() as cursor:
            request = """
INSERT INTO l_animation_song (animation_id, song_id)
     VALUES (%s, %s)
"""
            params = [self.animation_id, song_id]

            create_SQL_log(code_file, "Animations.new_song", "INSERT_2", request, params)
            cursor.execute(request, params)

        with connection.cursor() as cursor:
            request = """
INSERT IGNORE INTO l_animation_song_verse (animation_song_id, verse_id)
         SELECT las.animation_song_id, lv.verse_id
           FROM l_animation_song las 
LEFT OUTER JOIN l_verses lv ON lv.song_id = las.song_id
"""
            params = []

            create_SQL_log(code_file, "Animations.new_song", "INSERT_3", request, params)
            cursor.execute(request, params)
            

    def update_song_num(self, animation_song_id, num):
        with connection.cursor() as cursor:
            request = """
UPDATE l_animation_song
   SET num = %s
 WHERE animation_song_id = %s
"""
            params = [num, animation_song_id]

            create_SQL_log(code_file, "Animations.update_song_num", "UPDATE_2", request, params)
            cursor.execute(request, params)
    

    def get_songs_already_in(self):
        with connection.cursor() as cursor:
            request = """
SELECT song_id
  FROM l_animation_song
 WHERE animation_id = %s
"""
            params = [self.animation_id]

            create_SQL_log(code_file, "Animations.get_songs_already_in", "SELECT_5", request, params)
            cursor.execute(request, params)
            rows = cursor.fetchall()
            return [row[0] for row in rows]
    

    def delete_song(self, animation_song_id):
        with connection.cursor() as cursor:
            request = """
DELETE FROM l_animation_song
      WHERE animation_song_id = %s
"""
            params = [animation_song_id]

            create_SQL_log(code_file, "Animations.delete_song", "DELETE_2", request, params)
            cursor.execute(request, params)
            rows = cursor.fetchall()
            return [row[0] for row in rows]
        

    def update_verse_selected(self, animation_song_id, verse_id, selected):
        with connection.cursor() as cursor:
            request = """
UPDATE l_animation_song_verse
   SET selected = %s
 WHERE animation_song_id = %s
   AND verse_id = %s
"""
            params = [selected, animation_song_id, verse_id]

            create_SQL_log(code_file, "Animations.update_verse_selected", "UPDATE_3", request, params)
            cursor.execute(request, params)