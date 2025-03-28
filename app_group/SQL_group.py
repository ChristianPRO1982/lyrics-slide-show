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
    def __init__(self, group_id=None, name=None, info=None, admin_email=None, admin_password=None):
        self.group_id = group_id
        self.name = name
        self.info = info
        self.admin_email = admin_email
        self.admin_password = admin_password


    @staticmethod
    def get_all_groups():
        request = """
  SELECT *
    FROM c_groups
ORDER BY name
"""
        params = []

        create_SQL_log(code_file, "Group.get_all_groups", "SELECT_1", request, params)
        with connection.cursor() as cursor:
            cursor.execute(request, params)
            rows = cursor.fetchall()
        return [{'group_id': row[0], 'name': row[1], 'info': row[2], 'login': row[3], 'token': row[4]} for row in rows]
    

    def save(self):
        with connection.cursor() as cursor:
            if self.group_id:
                request = """
UPDATE c_groups
   SET name = %s,
       info = %s,
       admin_email = %s,
       admin_password = %s
 WHERE group_id = %s
"""
                params = [self.name, self.info, self.admin_email, self.token, self.group_id]
                
                create_SQL_log(code_file, "Group.save", "UPDATE_1", request, params)
                cursor.execute(request, params)

            else:
                request = """
INSERT INTO c_groups (name, info, admin_email, admin_password)
     VALUES (%s, %s, %s, %s)
"""
                params = [self.name, self.info, self.admin_email, self.admin_password]
                
                create_SQL_log(code_file, "Group.save", "INSERT_1", request, params)
                cursor.execute(request, params)
                self.group_id = cursor.lastrowid