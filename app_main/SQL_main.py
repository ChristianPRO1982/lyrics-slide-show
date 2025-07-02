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
        self.search_txt = None
        self.search_everywhere = None
        self.search_logic = None
        self.search_genres = None
        self.search_song_approved = None
        self.first_name = None
        self.last_name = None
        self.is_superuser = None
        self.is_staff = None

        self.get_user_by_username()
        if self.theme is None:
            self.init_c_user()


    def get_user_by_username(self):
        request = """
    SELECT cu.theme, cu.search_txt, cu.search_everywhere, cu.search_logic, cu.search_genres, cu.search_song_approved,
           au.first_name, au.last_name, au.is_superuser, au.is_staff
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
            self.search_txt = row[1]
            self.search_everywhere = row[2]
            self.search_logic = row[3]
            self.search_genres = row[4]
            self.search_song_approved = row[5]
            self.first_name = row[6]
            self.last_name = row[7]
            self.is_superuser = row[8]
            self.is_staff = row[9]


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
   SET theme = %s,
       search_txt = %s,
       search_everywhere = %s,
       search_logic = %s,
       search_genres = %s,
       search_song_approved = %s
 WHERE username = %s
"""
        params = [
            self.theme,
            self.search_txt,
            self.search_everywhere,
            self.search_logic,
            self.search_genres,
            self.search_song_approved,
            self.username
            ]

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


    def get_approved_songs_stats(self):
        request = """
SELECT SUM(CASE WHEN status > 0 THEN 1 ELSE 0 END) AS active_count,
       COUNT(*) AS total_count,
       ROUND(CASE WHEN COUNT(*) = 0 THEN 0
                  ELSE SUM(CASE WHEN status = 1 THEN 1 ELSE 0 END) / COUNT(*) * 100.0
             END, 2) AS active_percent
  FROM l_songs
"""
        params = []

        create_SQL_log(code_file, "Songs.get_approved_songs_stats", "SELECT_5", request, params)
        with connection.cursor() as cursor:
            cursor.execute(request, params)
            row = cursor.fetchone()
        self.songs_stats = {
            'approved_songs': int(row[0]) if row[0] is not None else 0,
            'total_songs': int(row[1]) if row[1] is not None else 0,
            'approved_percent': float(row[2]) if row[2] is not None else 0.0
        } if row else {
            'approved_songs': 0,
            'total_songs': 0,
            'approved_percent': 0.0
        }


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



##############################################
##############################################
#################### BAND ####################
##############################################
##############################################
class Band:
    def __init__(self, band_id=None, name=None, description=None):
        self.band_id = band_id
        self.name = name

        if band_id is not None and name is None:
            self.get_band_by_id()


    def get_band_by_id(self):
        request = """
SELECT band_id, name
  FROM c_bands
 WHERE band_id = %s
"""
        params = [self.band_id]

        create_SQL_log(code_file, "Band.get_band_by_id", "SELECT_6", request, params)
        with connection.cursor() as cursor:
            try:
                cursor.execute(request, params)
                row = cursor.fetchone()
            except Exception as e:
                row = None
        if row:
            self.band_id = row[0]
            self.name = row[1]


    @staticmethod
    def get_all_bands():
        request = """
SELECT band_id, name
  FROM c_bands
 ORDER BY name
"""
        params = []

        create_SQL_log(code_file, "Band.get_all_bands", "SELECT_7", request, params)
        with connection.cursor() as cursor:
            cursor.execute(request, params)
            rows = cursor.fetchall()
        return [Band(band_id=row[0], name=row[1]) for row in rows] if rows else []
    

    def save(self):
        if self.band_id is None:
            request = """
INSERT INTO c_bands (name)
     VALUES (%s)
"""
            params = [self.name]

            create_SQL_log(code_file, "Band.save", "INSERT_2", request, params)
            with connection.cursor() as cursor:
                try:
                    cursor.execute(request, params)
                    self.band_id = cursor.lastrowid  # Get the last inserted ID
                    return ''
                except Exception as e:
                    if 'Duplicate entry' in str(e):
                        return '[ERR41]'
                    return '[ERR42]'
                
        else:
            request = """
UPDATE c_bands
   SET name = %s
 WHERE band_id = %s
"""
            params = [self.name, self.band_id]

            create_SQL_log(code_file, "Band.save", "UPDATE_4", request, params)
            with connection.cursor() as cursor:
                try:
                    cursor.execute(request, params)
                    return ''
                except Exception as e:
                    if 'Duplicate entry' in str(e):
                        return '[ERR41]'
                    return '[ERR43]'
    

    def delete_band(self):
        request = """
DELETE FROM c_bands
 WHERE band_id = %s
"""
        params = [self.band_id]

        create_SQL_log(code_file, "Band.delete_band", "DELETE_1", request, params)
        with connection.cursor() as cursor:
            try:
                cursor.execute(request, params)
                return ''
            except Exception as e:
                return '[ERR40]'
            


################################################
################################################
#################### ARTIST ####################
################################################
################################################
class Artist:
    def __init__(self, artist_id=None, name=None):
        self.artist_id = artist_id
        self.name = name

        if artist_id is not None and name is None:
            self.get_artist_by_id()


    def get_artist_by_id(self):
        request = """
SELECT artist_id, name
  FROM c_artists
 WHERE artist_id = %s
"""
        params = [self.artist_id]

        create_SQL_log(code_file, "Artist.get_artist_by_id", "SELECT_8", request, params)
        with connection.cursor() as cursor:
            try:
                cursor.execute(request, params)
                row = cursor.fetchone()
            except Exception as e:
                row = None
        if row:
            self.artist_id = row[0]
            self.name = row[1]
        

    @staticmethod
    def get_all_artists():
        request = """
SELECT artist_id, name
  FROM c_artists
 ORDER BY name
"""
        params = []

        create_SQL_log(code_file, "Artist.get_all_artists", "SELECT_9", request, params)
        with connection.cursor() as cursor:
            cursor.execute(request, params)
            rows = cursor.fetchall()
        return [Artist(artist_id=row[0], name=row[1]) for row in rows] if rows else []
    

    def save(self):
        if self.artist_id is None:
            request = """
INSERT INTO c_artists (name)
     VALUES (%s)
"""
            params = [self.name]

            create_SQL_log(code_file, "Artist.save", "INSERT_3", request, params)
            with connection.cursor() as cursor:
                try:
                    cursor.execute(request, params)
                    self.artist_id = cursor.lastrowid  # Get the last inserted ID
                    return ''
                except Exception as e:
                    if 'Duplicate entry' in str(e):
                        return '[ERR44]'
                    return '[ERR45]'

        else:
            request = """
UPDATE c_artists
   SET name = %s
 WHERE artist_id = %s
"""
            params = [self.name, self.artist_id]

            create_SQL_log(code_file, "Artist.save", "UPDATE_5", request, params)
            with connection.cursor() as cursor:
                try:
                    cursor.execute(request, params)
                    return ''
                except Exception as e:
                    if 'Duplicate entry' in str(e):
                        return '[ERR44]'
                    return '[ERR46]'
                

    def delete_artist(self):
        request = """
DELETE FROM c_artists
 WHERE artist_id = %s
"""
        params = [self.artist_id]

        create_SQL_log(code_file, "Artist.delete_artist", "DELETE_2", request, params)
        with connection.cursor() as cursor:
            try:
                cursor.execute(request, params)
                return ''
            except Exception as e:
                return '[ERR47]'