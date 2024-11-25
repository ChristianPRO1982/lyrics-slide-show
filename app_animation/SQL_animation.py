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