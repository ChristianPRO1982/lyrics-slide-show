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
        self.search_bands = None
        self.search_artists = None
        self.search_song_approved = None
        self.first_name = None
        self.last_name = None
        self.email = None
        self.is_superuser = None
        self.is_staff = None

        self.get_user_by_username()
        if self.theme is None:
            self.init_c_user()


    def get_user_by_username(self):
        request = """
    SELECT cu.theme, cu.search_txt, cu.search_everywhere, cu.search_logic,
           cu.search_genres, cu.search_bands, cu.search_artists,
           cu.search_song_approved,
           au.first_name, au.last_name, au.email, au.is_superuser, au.is_staff
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
            self.search_bands = row[5]
            self.search_artists = row[6]
            self.search_song_approved = row[7]
            self.first_name = row[8]
            self.last_name = row[9]
            self.email = row[10]
            self.is_superuser = row[11]
            self.is_staff = row[12]


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
       search_bands = %s,
       search_artists = %s,
       search_song_approved = %s
 WHERE username = %s
"""
        params = [
            self.theme,
            self.search_txt,
            self.search_everywhere,
            self.search_logic,
            self.search_genres,
            self.search_bands,
            self.search_artists,
            self.search_song_approved,
            self.username
            ]

        create_SQL_log(code_file, "User.save", "UPDATE_1", request, params)
        with connection.cursor() as cursor:
            cursor.execute(request, params)


    def save_profil(self):
        request = """
UPDATE auth_user
   SET first_name = %s,
       last_name = %s
 WHERE username = %s
"""
        params = [self.first_name, self.last_name, self.username]

        create_SQL_log(code_file, "User.save_profil", "UPDATE_2", request, params)
        with connection.cursor() as cursor:
            cursor.execute(request, params)


    def change_email(self, new_email, token):
        request = """
INSERT INTO c_user_change_email (username, token, create_time, last_email, new_email)
     VALUES (%s, %s, NOW(), %s, %s)
"""
        params = [self.username, token, self.email, new_email]

        create_SQL_log(code_file, "User.change_email", "INSERT_4", request, params)
        with connection.cursor() as cursor:
            try:
                cursor.execute(request, params)
                return ''
            except Exception as e:
                return '[ERR50]'
            

    @staticmethod
    def save_new_email(username: str, new_email: str):
        request = """
UPDATE auth_user
   SET email = %s
 WHERE username = %s
"""
        params = [new_email, username]

        create_SQL_log(code_file, "User.save_new_email", "UPDATE_7", request, params)
        with connection.cursor() as cursor:
            try:
                cursor.execute(request, params)
                return True
            except Exception as e:
                return False
            

    @staticmethod
    def checking_email(md5_last_email, md5_new_email, token):
        request = """
SELECT username, new_email
  FROM c_user_change_email
 WHERE md5(last_email) = %s
   AND md5(new_email) = %s
   AND token = %s
   AND create_time > NOW() - INTERVAL 2 HOUR
"""
        params = [md5_last_email, md5_new_email, token]

        create_SQL_log(code_file, "User.checking_email", "SELECT_10", request, params)
        with connection.cursor() as cursor:
            try:
                cursor.execute(request, params)
                row = cursor.fetchone()
                if row:
                    return User.save_new_email(row[0], row[1])
                else:
                    return None
            except Exception as e:
                return None
            


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
    def __init__(self, language):
        self.language = language.upper()
        self.get_site_info()


    def get_site_info(self):
        request = """
SELECT *
  FROM l_site_params
 WHERE language = %s
"""
        params = [self.language]

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
            self.verse_max_lines = row[6]
            self.verse_max_characters_for_a_line = row[7]
            self.chorus_prefix = row[8]
            self.verse_prefix1 = row[9]
            self.verse_prefix2 = row[10]
            self.admin_message = row[11]
            self.moderator_message = row[12]
        else:
            self.language = "FR"
            self.title = "Bienvenue !"
            self.title_h1 = "Bienvenue !"
            self.home_text = ""
            self.bloc1_text = ""
            self.bloc2_text = ""
            self.verse_max_lines = 10
            self.verse_max_characters_for_a_line = 60
            self.chorus_prefix = "R. "
            self.verse_prefix1 = "C"
            self.verse_prefix2 = ". "
            self.admin_message = ""
            self.moderator_message = ""


    def save(self):
        request = """
UPDATE l_site_params
   SET title = %s,
       title_h1 = %s,
       home_text = %s,
       bloc1_text = %s,
       bloc2_text = %s,
       verse_max_lines = %s,
       verse_max_characters_for_a_line = %s,
       chorus_prefix = %s,
       verse_prefix1 = %s,
       verse_prefix2 = %s,
       admin_message = %s,
       moderator_message = %s
 WHERE language = %s
"""
        params = [
            self.title, self.title_h1, self.home_text, self.bloc1_text, self.bloc2_text,
            self.verse_max_lines, self.verse_max_characters_for_a_line,
            self.chorus_prefix, self.verse_prefix1, self.verse_prefix2,
            self.admin_message, self.moderator_message,
            self.language
        ]

        create_SQL_log(code_file, "Site.save", "UPDATE_3", request, params)
        with connection.cursor() as cursor:
            cursor.execute(request, params)


    def get_site_messages(self, moderator):
        messages = self.admin_message
        if moderator and self.moderator_message:
            if messages: messages += '<hr>'
            messages += self.moderator_message
        return messages


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

            create_SQL_log(code_file, "Band.save", "UPDATE_5", request, params)
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

            create_SQL_log(code_file, "Artist.save", "UPDATE_6", request, params)
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
            


############################################
############################################
#################### DB ####################
############################################
############################################
class DB:
    @staticmethod
    def c_user_change_email():
        request = """
DELETE FROM c_user_change_email
      WHERE create_time < NOW() - INTERVAL 2 HOUR
"""
        params = []

        create_SQL_log(code_file, "DB.c_user_change_email", "DELETE_3", request, params)
        with connection.cursor() as cursor:
            try:
                cursor.execute(request, params)
                return ''
            except Exception as e:
                return '[ERR51]'