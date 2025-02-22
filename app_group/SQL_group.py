from typing import Any
from django.db import connection
from app_logs.utils import create_SQL_log



code_file = "SQL_group.py"


###############################################
###############################################
#################### GROUP ####################
###############################################
###############################################
class Group:
    def __init__(self, song_id=None, name=None, info=None, login=None, token=None):
        self.song_id = song_id
        self.name = name
        self.info = info
        self.login = login
        self.token = token


    @staticmethod
    def get_all_groups():
        request = """
  SELECT *
    FROM c_groups
ORDER BY name
"""
        params = []

        create_SQL_log(code_file, "Song.get_all_songs", "SELECT_1", request, params)
        with connection.cursor() as cursor:
            cursor.execute(request, params)
            rows = cursor.fetchall()
        return [{'song_id': row[0], 'title': row[1], 'sub_title': row[2], 'description': row[3], 'artist': row[4], 'full_title': row[5]} for row in rows]