from django.db import connection
from app_logs.utils import create_SQL_log
from app_song.SQL_song import Song



code_file = "SQL_main.py"


##############################################
##############################################
#################### USER ####################
##############################################
##############################################
class User:
    def __init__(self, username):
        self.username = username
        self.theme = None
        self.first_name = None
        self.last_name = None
        self.is_superuser = None
        self.is_staff = None

        self.get_user_by_username()
        if self.theme is None:
            self.init_c_user()


    def get_user_by_username(self):
        request = """
    SELECT cu.theme, au.first_name, au.last_name, au.is_superuser, au.is_staff
      FROM c_users cu
RIGHT JOIN auth_user au ON au.username = cu.username
     WHERE au.username = %s
     LIMIT 1
"""
        params = [self.username]

        create_SQL_log(code_file, "User.get_user_by_username", "SELECT_1", request, params)
        with connection.cursor() as cursor:
            cursor.execute(request, params)
            row = cursor.fetchone()
        if row:
            self.theme = row[0]
            self.first_name = row[1]
            self.last_name = row[2]
            self.is_superuser = row[3]
            self.is_staff = row[4]


    def init_c_user(self):
        request = """
INSERT INTO c_users (username)
     VALUES (%s)
    """
        params = [self.username]

        create_SQL_log(code_file, "User.init_c_user", "INSERT_1", request, params)
        with connection.cursor() as cursor:
            cursor.execute(request, params)


    def save(self):
        request = """
UPDATE c_users
   SET theme = %s
 WHERE username = %s
"""
        params = [self.theme, self.username]

        create_SQL_log(code_file, "User.save", "UPDATE_1", request, params)
        with connection.cursor() as cursor:
            cursor.execute(request, params)


##############################################
##############################################
#################### SONG ####################
##############################################
##############################################
class Songs:
    def __init__(self):
        self.get_songs_to_be_moderated()


    def get_songs_to_be_moderated(self):
        request = """
SELECT song_id,
       CONCAT(title,
              CASE
                  WHEN sub_title != '' THEN CONCAT(' - ', sub_title)
                  ELSE ''
              END,
              CASE
                  WHEN artist != '' THEN CONCAT(' [', artist, ']')
                  ELSE ''
              END) AS full_title,
       description
  FROM l_songs
 WHERE status IN (2)
"""
        params = []

        create_SQL_log(code_file, "Songs.get_songs_to_be_moderated", "SELECT_2", request, params)
        with connection.cursor() as cursor:
            cursor.execute(request, params)
            rows = cursor.fetchall()
        self.songs = [Song(song_id=row[0], full_title=row[1], description=row[2]) for row in rows] if rows else []


##############################################
##############################################
#################### SITE ####################
##############################################
##############################################
class Site:
    def __init__(self):
        self.get_site_info()
        self.get_site_parameters()


    def get_site_info(self):
        request = """
SELECT *
  FROM l_site
"""
        params = []

        create_SQL_log(code_file, "Site.get_site_info", "SELECT_3", request, params)
        with connection.cursor() as cursor:
            cursor.execute(request, params)
            row = cursor.fetchone()
        if row:
            self.language = row[0]
            self.title = row[1]
            self.title_h1 = row[2]
            self.home_text = row[3]
            self.bloc1_text = row[4]
            self.bloc2_text = row[5]
        else:
            self.language = "EN"
            self.title = "Welcome!"
            self.title_h1 = "Welcome!"
            self.home_text = ""
            self.bloc1_text = ""
            self.bloc2_text = ""


    def get_site_parameters(self):
        request = """
SELECT *
  FROM l_site_params
"""
        params = []

        create_SQL_log(code_file, "Site.get_site_parameters", "SELECT_4", request, params)
        with connection.cursor() as cursor:
            cursor.execute(request, params)
            row = cursor.fetchone()
        if row:
            self.verse_max_lines = row[0]
            self.verse_max_characters_for_a_line = row[1]
        else:
            self.verse_max_lines = 10
            self.verse_max_characters_for_a_line = 60


    def save(self):
        request = """
UPDATE l_site
   SET language = %s,
       title = %s,
       title_h1 = %s,
       home_text = %s,
       bloc1_text = %s,
       bloc2_text = %s
"""
        params = [self.language, self.title, self.title_h1, self.home_text, self.bloc1_text, self.bloc2_text]

        create_SQL_log(code_file, "Site.save", "UPDATE_2", request, params)
        with connection.cursor() as cursor:
            cursor.execute(request, params)

        request = """
UPDATE l_site_params
   SET verse_max_lines = %s,
       verse_max_characters_for_a_line = %s
"""
        params = [self.verse_max_lines, self.verse_max_characters_for_a_line]

        create_SQL_log(code_file, "Site.save", "UPDATE_3", request, params)
        with connection.cursor() as cursor:
            cursor.execute(request, params)