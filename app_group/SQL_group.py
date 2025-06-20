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
    def get_all_groups(username):
        request = """
   SELECT cg.*, COUNT(cgu.username) AS member, COUNT(cguatj.username) AS ask_member
     FROM c_groups cg
LEFT JOIN c_group_user cgu ON cgu.group_id = cg.group_id
                          AND cgu.username = %s
LEFT JOIN c_group_user_ask_to_join cguatj ON cguatj.group_id = cg.group_id
                                         AND cguatj.username = %s
 GROUP BY cg.group_id, cg.name, cg.info, cg.token, cg.private
 ORDER BY name
"""
        params = [username, username]

        create_SQL_log(code_file, "Group.get_all_groups", "SELECT_1", request, params)
        with connection.cursor() as cursor:
            cursor.execute(request, params)
            rows = cursor.fetchall()
        return [{'group_id': row[0], 'name': row[1], 'info': row[2], 'token': row[3], 'private': row[4], 'member': row[5], 'ask_member': row[6]} for row in rows]
    

    def save(self):
        if self.token == '':
            self.token = None

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
        

    def get_group_by_id(group_id, url_token, username, is_moderator):
        if is_moderator:
            moderator = 1
        else:
            moderator = 0

        request = """
SELECT *
  FROM c_groups cg
 WHERE cg.group_id = %s
   AND (
           cg.private = 0 AND cg.token IS NULL
        OR cg.token = %s
        OR %s IN (SELECT username FROM c_group_user cgu WHERE cgu.group_id = %s)
        OR 1 = %s
       )
"""
        params = [group_id, url_token, username, group_id, moderator]

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
        

    def get_admin_group_by_id(group_id, username, is_moderator):
        if is_moderator:
            moderator = 1
        else:
            moderator = 0

        request = """
SELECT *
  FROM c_groups cg
 WHERE cg.group_id = %s
   AND (%s IN (SELECT username
                FROM c_group_user cgu
               WHERE cgu.group_id = %s
                 AND cgu.admin = 1)
       OR 1 = %s)
"""
        params = [group_id, username, group_id, moderator]

        create_SQL_log(code_file, "Group.get_group_by_id", "SELECT_4", request, params)
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
        

    def delete_group(self):
        request = """
DELETE FROM c_groups
 WHERE group_id = %s
"""
        params = [self.group_id]

        create_SQL_log(code_file, "Group.delete_group", "DELETE_1", request, params)
        try:
            with connection.cursor() as cursor:
                cursor.execute(request, params)
            return True
        except Exception as e:
            return False
        

    def get_list_of_members(self):
        request = """
  SELECT cgu.admin, cgu.username, CONCAT(cgu.username, ' (',au.first_name, ' - ', au.last_name, ')') AS full_name
    FROM c_groups cg
    JOIN c_group_user cgu ON cgu.group_id = cg.group_id
    JOIN auth_user au ON au.username = cgu.username
   WHERE cg.group_id = %s
ORDER BY cgu.admin DESC, full_name
"""
        params = [self.group_id]

        create_SQL_log(code_file, "Group.get_list_of_members", "SELECT_5", request, params)
        try:
            with connection.cursor() as cursor:
                cursor.execute(request, params)
                rows = cursor.fetchall()
            return [{'admin': row[0], 'username': row[1], 'full_name': row[2]} for row in rows]
        except Exception as e:
            return []
        

    def nb_admins(self):
        request = """
SELECT COUNT(*)
  FROM c_group_user
 WHERE group_id = %s
   AND admin = 1
"""
        params = [self.group_id]
        create_SQL_log(code_file, "Group.nb_admin_members", "SELECT_7", request, params)
        try:
            with connection.cursor() as cursor:
                cursor.execute(request, params)
                count = cursor.fetchone()[0]
            return count
        except Exception as e:
            return 0
        

    def get_list_ask_to_be_member(self):
        request = """
SELECT username
  FROM c_group_user_ask_to_join cguatj 
 WHERE group_id = %s
"""
        params = [self.group_id]

        create_SQL_log(code_file, "Group.get_list_ask_to_be_member", "SELECT_6", request, params)
        try:
            with connection.cursor() as cursor:
                cursor.execute(request, params)
                rows = cursor.fetchall()
            return [{'username': row[0]} for row in rows]
        except Exception as e:
            return []
        

    @staticmethod
    def ask_to_join(group_id, username):
        request = """
INSERT INTO c_group_user_ask_to_join (group_id, username)
     VALUES (%s, %s)
"""
        params = [group_id, username]

        create_SQL_log(code_file, "Group.ask_to_join", "INSERT_3", request, params)
        try:
            with connection.cursor() as cursor:
                cursor.execute(request, params)
            return True
        except Exception as e:
            return False
        

    def add_member(self, username):
        request = """
INSERT INTO c_group_user (group_id, username, admin)
     VALUES (%s, %s, 0)
"""
        params = [self.group_id, username]

        create_SQL_log(code_file, "Group.add_member", "INSERT_4", request, params)
        try:
            with connection.cursor() as cursor:
                cursor.execute(request, params)
                self.clean_ask_to_join()
            return True
        except Exception as e:
            return False
        

    def delete_member(self, username):
        request = """
DELETE FROM c_group_user
 WHERE group_id = %s
   AND username = %s
"""
        params = [self.group_id, username]

        create_SQL_log(code_file, "Group.delete_member", "DELETE_2", request, params)
        try:
            with connection.cursor() as cursor:
                cursor.execute(request, params)
            return True
        except Exception as e:
            return False
        

    def clean_ask_to_join(self):
        request = """
DELETE
  FROM c_group_user_ask_to_join cguatj
 WHERE (cguatj.group_id, cguatj.username) IN (SELECT cgu.group_id, cgu.username
                                                FROM c_group_user cgu)
"""
        params = []

        create_SQL_log(code_file, "Group.clean_ask_to_join", "DELETE_3", request, params)
        try:
            with connection.cursor() as cursor:
                cursor.execute(request, params)
            return True
        except Exception as e:
            return False