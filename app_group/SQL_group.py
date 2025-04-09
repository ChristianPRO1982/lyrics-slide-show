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
    def __init__(self, group_id=None, name=None, info=None, token=None, private=None):
        self.group_id = group_id
        self.name = name
        self.info = info
        self.token = token
        self.private = private


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
        return [{'group_id': row[0], 'name': row[1], 'info': row[2], 'token': row[3], 'private': row[4]} for row in rows]
    

    def save(self):
        with connection.cursor() as cursor:
            if self.group_id:
                request = """
UPDATE c_groups
   SET name = %s,
       info = %s,
       token = %s,
       private = %s
 WHERE group_id = %s
"""
                params = [self.name, self.info, self.token, self.private, self.group_id]
                
                create_SQL_log(code_file, "Group.save", "UPDATE_1", request, params)
                cursor.execute(request, params)

            else:
                try:
                    request = """
INSERT INTO c_groups (name, info)
     VALUES (%s, %s)
"""
                    params = [self.name, self.info]
                    
                    create_SQL_log(code_file, "Group.save", "INSERT_1", request, params)
                    cursor.execute(request, params)
                    self.group_id = cursor.lastrowid

                    return ''

                except Exception as e:
                    if 'Duplicate entry' in str(e):
                        return "[ERR8]"
                    return "[ERR9]"


    def add_admin(self, username, admin=0):
        try:
            request = """
SELECT COUNT(1)
  FROM auth_user
 WHERE username = %s
        """
            params = [username]

            create_SQL_log(code_file, "Group.add_admin", "SELECT_2", request, params)
            with connection.cursor() as cursor:
                cursor.execute(request, params)
                count = cursor.fetchone()[0]
            
            if count == 0:
                raise Exception('DB_ERR_1')
            
            request = """
INSERT INTO c_group_user
     VALUES (%s, %s, %s)
"""
            params = [self.group_id, username, admin]

            try:
                create_SQL_log(code_file, "Group.add_admin", "INSERT_2", request, params)
                with connection.cursor() as cursor:
                    cursor.execute(request, params)
            except Exception as e:
                return "[ERR7]"
            
            return ''
            
        except Exception as e:
            if 'DB_ERR_1' in str(e):
                return "[ERR5]"
            return "[ERR6]"
        

    def get_group_by_id(group_id, url_token, username):
        request = """
SELECT *
  FROM c_groups cg
 WHERE cg.group_id = %s
   AND (
           cg.private = 0 AND cg.token = ''
        OR cg.private = 0 AND cg.token = %s
        OR %s IN (SELECT username FROM c_group_user cgu WHERE cgu.group_id = %s)
       )
"""
        params = [group_id, url_token, username, group_id]

        create_SQL_log(code_file, "Group.get_group_by_id", "SELECT_3", request, params)
        try:
            with connection.cursor() as cursor:
                cursor.execute(request, params)
                row = cursor.fetchone()
            
            if row:
                return Group(group_id=row[0], name=row[1], info=row[2], token=row[3], private=row[4])
            else:
                return 0
        
        except Exception as e:
            return None
        

    def get_admin_group_by_id(group_id, username):
        request = """
SELECT *
  FROM c_groups cg
 WHERE cg.group_id = %s
   AND %s IN (SELECT username
                FROM c_group_user cgu
               WHERE cgu.group_id = %s
                 AND cgu.admin = 1)
"""
        params = [group_id, username, group_id]

        create_SQL_log(code_file, "Group.get_group_by_id", "SELECT_3", request, params)
        try:
            with connection.cursor() as cursor:
                cursor.execute(request, params)
                row = cursor.fetchone()
            
            if row:
                return Group(group_id=row[0], name=row[1], info=row[2], token=row[3], private=row[4])
            else:
                return 0
        
        except Exception as e:
            return None