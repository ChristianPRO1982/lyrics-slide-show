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