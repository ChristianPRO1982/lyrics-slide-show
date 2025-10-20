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
    def __init__(self, animation_id=None, group_id=None, name=None, description=None, date=None,
                 color_rgba=None, bg_rgba=None, font=None, font_size=None, padding=None):
        self.animation_id = animation_id
        self.group_id = group_id
        self.name = name
        self.description = description
        self.date = date
        self.color_rgba = color_rgba
        self.bg_rgba = bg_rgba
        self.font = font
        self.font_size = font_size
        self.padding = padding
        self.songs = []
        self.all_songs()
        self.verses = []
        self.all_verses()
        self.colors = []
        self.all_colors()


    @staticmethod
    def get_all_animations(group_id):
        request = """
  SELECT animation_id, group_id, name, description, date,
         CASE
              WHEN DATEDIFF(date, SYSDATE()) >= 0 THEN TRUE
              ELSE FALSE
         END AS future
    FROM l_animations
   WHERE group_id = %s
ORDER BY date, name
"""
        params = [group_id]

        create_SQL_log(code_file, "Animations.get_all_animations", "SELECT_1", request, params)
        with connection.cursor() as cursor:
            cursor.execute(request, params)
            rows = cursor.fetchall()
        return [{'animation_id': row[0], 'group_id': row[1], 'name': row[2], 'description': row[3], 'date': row[4], 'future': row[5]} for row in rows]
    

    @classmethod
    def get_animation_by_id(cls, animation_id, group_id):
        with connection.cursor() as cursor:
            request = """
SELECT *
  FROM l_animations
 WHERE animation_id = %s
   AND group_id = %s
"""
            params = [animation_id, group_id]
            
            create_SQL_log(code_file, "Animations.get_animation_by_id", "SELECT_2", request, params)
            cursor.execute(request, params)
            row = cursor.fetchone()
        if row:
            return cls(animation_id=row[0],
                       group_id=row[1],
                       name=row[2],
                       description=row[3],
                       date=row[4],
                       color_rgba=row[5],
                       bg_rgba=row[6],
                       font=row[7],
                       font_size=row[8],
                       padding=row[9])
        return None
    

    @classmethod
    def get_animation_by_id_without_group_id(cls, animation_id):
        with connection.cursor() as cursor:
            request = """
SELECT animation_id, name
  FROM l_animations
 WHERE animation_id = %s
"""
            params = [animation_id]
            
            create_SQL_log(code_file, "Animations.get_animation_by_id", "SELECT_10", request, params)
            cursor.execute(request, params)
            row = cursor.fetchone()
        if row:
            return cls(animation_id=row[0],
                       name=row[1])
        return None


    def save(self):
        with connection.cursor() as cursor:
            if self.animation_id:
                request = f"""
UPDATE l_animations
   SET name = %s,
       description = %s,
       date = %s,
       color_rgba = %s,
       bg_rgba = %s,
       font = %s,
       font_size = %s,
       padding = %s
 WHERE animation_id = %s
"""
                params = [self.name, self.description, self.date,
                          self.color_rgba, self.bg_rgba, self.font, self.font_size,
                          self.padding,
                          self.animation_id]
                
                create_SQL_log(code_file, "Animations.save", "UPDATE_1", request, params)
                cursor.execute(request, params)

            else:
                request = """
INSERT INTO l_animations (group_id, name, description, date)
     VALUES (%s, %s, %s, %s)
"""
                params = [self.group_id, self.name, self.description, self.date]
                
                create_SQL_log(code_file, "Animations.save", "INSERT_1", request, params)
                cursor.execute(request, params)
                self.animation_id = cursor.lastrowid


    def delete(self):
        if not self.animation_id:
            raise ValueError("L'ID de l'animation est requis pour la supprimer.")
        with connection.cursor() as cursor:
            request = """
DELETE FROM l_animations
      WHERE animation_id = %s
"""
            params = [self.animation_id]

            create_SQL_log(code_file, "Animations.delete", "DELETE_1", request, params)
            cursor.execute(request, params)


    def all_songs(self):
        if self.animation_id:
            with connection.cursor() as cursor:
                request = """
    SELECT las.animation_song_id, las.animation_id, las.song_id, las.num,
  		 CASE 
              WHEN las.color_rgba IS NOT NULL AND las.color_rgba != '' THEN las.color_rgba
              ELSE la.color_rgba
         END AS final_color_rgba,
  		 CASE 
              WHEN las.bg_rgba IS NOT NULL AND las.bg_rgba != '' THEN las.bg_rgba
              ELSE la.bg_rgba
         END AS final_bg_rgba,
  		 CASE 
              WHEN las.font IS NOT NULL AND las.font != '' THEN las.font
              ELSE la.font
         END AS final_font,
         las.font,
         las.font_size,
         ROUND(las.num / 2, 0) as numD2,
         CONCAT(
                ls.title,
                CASE
                    WHEN ls.sub_title != '' THEN CONCAT(' - ', ls.sub_title)
                    ELSE ''
                END) AS full_title
    FROM l_animation_song las
    JOIN l_animations la ON la.animation_id = las.animation_id
    JOIN l_songs ls ON las.song_id = ls.song_id
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
                        'color_rgba': row[4],
                        'bg_rgba': row[5],
                        'final_font': row[6],
                        'font': row[7],
                        'font_size': row[8],
                        'numD2': row[9],
                        'full_title': row[10],
                    } for row in rows]


    def all_verses(self):
        if self.animation_id:
            with connection.cursor() as cursor:
                request = """
  SELECT lasv.animation_song_id,
         lasv.verse_id,
         lasv.selected,
         CASE 
              WHEN lasv.color_rgba IS NOT NULL AND lasv.color_rgba != '' THEN lasv.color_rgba
              WHEN las.color_rgba IS NOT NULL AND las.color_rgba != '' THEN las.color_rgba
              ELSE la.color_rgba
         END AS final_color_rgba,
         CASE 
              WHEN lasv.bg_rgba IS NOT NULL AND lasv.bg_rgba != '' THEN lasv.bg_rgba
              WHEN las.bg_rgba IS NOT NULL AND las.bg_rgba != '' THEN las.bg_rgba
              ELSE la.bg_rgba
         END final_bg_rgba,
         CASE 
              WHEN lasv.font IS NOT NULL AND lasv.font != '' THEN lasv.font
              WHEN las.font IS NOT NULL AND las.font != '' THEN las.font
              ELSE la.font
         END final_font,
         lasv.font,
         lasv.font_size,
         lv.num_verse,
         lv.text
    FROM l_animation_song_verse lasv
    JOIN l_animation_song las ON las.animation_song_id = lasv.animation_song_id
    JOIN l_animations la ON la.animation_id = las.animation_id
    JOIN l_verses lv ON lv.verse_id = lasv.verse_id
   WHERE lv.chorus <> 1
     AND la.animation_id = %s
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
                        'color_rgba': row[3],
                        'bg_rgba': row[4],
                        'final_font': row[5],
                        'font': row[6],
                        'font_size': row[7],
                        'num_verse': row[8],
                        'text': row[9],
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
        
        self.new_song_verses_all()


    def new_song_verses_all(self):
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
            

    def update_animation_song(self, animation_song_id, num, font, font_size, change_colors):
        if len(change_colors) == 2:
            self.update_animation_song_colors(animation_song_id, change_colors[0], change_colors[1])
        with connection.cursor() as cursor:
            request = """
UPDATE l_animation_song
   SET num = %s,
       font = %s,
       font_size = %s
 WHERE animation_song_id = %s
"""
            params = [num, font, font_size, animation_song_id]

            create_SQL_log(code_file, "Animations.update_animation_song", "UPDATE_4", request, params)
            cursor.execute(request, params)
            

    def update_animation_song_colors(self, animation_song_id, color_rgba, bg_rgba):
        with connection.cursor() as cursor:
            request = """
UPDATE l_animation_song
   SET color_rgba = %s,
       bg_rgba = %s
 WHERE animation_song_id = %s
"""
            params = [color_rgba, bg_rgba, animation_song_id]

            create_SQL_log(code_file, "Animations.update_animation_song", "UPDATE_5", request, params)
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
        

    def update_animation_verse(self, animation_song_id, verse_id, selected, font, font_size, change_colors):
        if len(change_colors) == 2:
            self.update_animation_verse_colors(animation_song_id, verse_id, change_colors[0], change_colors[1])
        with connection.cursor() as cursor:
            request = """
UPDATE l_animation_song_verse
   SET selected = %s,
       font = %s,
       font_size = %s
 WHERE animation_song_id = %s
   AND verse_id = %s
"""
            params = [selected, font, font_size, animation_song_id, verse_id]

            create_SQL_log(code_file, "Animations.update_verse", "UPDATE_3", request, params)
            try:
                cursor.execute(request, params)
                return True
            except Exception as e:
                return False
        

    def update_animation_verse_colors(self, animation_song_id, verse_id, color_rgba, bg_rgba):
        with connection.cursor() as cursor:
            request = """
UPDATE l_animation_song_verse
   SET color_rgba = %s,
       bg_rgba = %s
 WHERE animation_song_id = %s
   AND verse_id = %s
"""
            params = [color_rgba, bg_rgba, animation_song_id, verse_id]

            create_SQL_log(code_file, "Animations.update_verse", "UPDATE_3", request, params)
            cursor.execute(request, params)


    def get_slides(self):
        with connection.cursor() as cursor:
            request = """
  SELECT lasv.animation_song_id,
         lasv.verse_id,
         CONCAT(
                ls.title,
                CASE
                     WHEN ls.sub_title != '' THEN CONCAT(' - ', ls.sub_title)
                     ELSE ''
                END) AS full_title,
         lv.chorus,
         lv.num_verse,
         lv.followed,
         REPLACE(REPLACE(REPLACE(lv.text, '\r\n', '<br>'), '\r', '<br>'), '\n', '<br>') text,
         CASE
              WHEN lag(lasv.animation_song_id) OVER (ORDER BY las.num, lv.num) != lasv.animation_song_id
                OR lag(lasv.animation_song_id) OVER (ORDER BY las.num, lv.num) IS NULL
              THEN TRUE
              ELSE FALSE
         END AS new_animation_song,
         CASE 
              WHEN lasv.color_rgba IS NOT NULL AND lasv.color_rgba != '' THEN lasv.color_rgba
              WHEN las.color_rgba IS NOT NULL AND las.color_rgba != '' THEN las.color_rgba
              ELSE la.color_rgba
         END AS final_color_rgba,
         CASE 
              WHEN lasv.bg_rgba IS NOT NULL AND lasv.bg_rgba != '' THEN lasv.bg_rgba
              WHEN las.bg_rgba IS NOT NULL AND las.bg_rgba != '' THEN las.bg_rgba
              ELSE la.bg_rgba
         END final_bg_rgba,
         CASE 
              WHEN lasv.font IS NOT NULL AND lasv.font != '' THEN lasv.font
              WHEN las.font IS NOT NULL AND las.font != '' THEN las.font
              ELSE la.font
         END AS final_font,
         la.font_size + las.font_size + lasv.font_size font_size
    FROM l_animation_song_verse lasv
    JOIN l_animation_song las ON las.animation_song_id = lasv.animation_song_id
    JOIN l_songs ls ON ls.song_id = las.song_id
    JOIN l_verses lv ON lv.verse_id = lasv.verse_id
    JOIN l_animations la ON la.animation_id = las.animation_id
   WHERE las.animation_id = %s
     AND lasv.selected IS TRUE
ORDER BY las.num, lv.num
"""
            params = [self.animation_id]

            create_SQL_log(code_file, "Animations.get_slides", "SELECT_6", request, params)

            try:
                cursor.execute(request, params)
                rows = cursor.fetchall()
                return [{
                        'animation_song_id': row[0],
                        'verse_id': row[1],
                        'full_title': row[2],
                        'chorus': row[3],
                        'num_verse': row[4],
                        'followed': row[5],
                        'text': row[6].replace(' :', '&nbsp;:').replace(' -', '&nbsp;-').replace(' ?', '&nbsp;?').replace(' !', '&nbsp;!').replace(' ;', '&nbsp;;'),
                        'new_animation_song': row[7],
                        'color_rgba': row[8],
                        'bg_rgba': row[9],
                        'font': row[10],
                        'font_size': row[11],
                    } for row in rows]
            
            except Exception as e:
                return None
            

    @staticmethod
    def get_animation_id_by_song_id(song_id):
        with connection.cursor() as cursor:
            request = """
SELECT animation_id
  FROM l_animation_song
 WHERE animation_song_id = %s
"""
            params = [song_id]

            create_SQL_log(code_file, "Animations.get_animation_id_by_song_id", "SELECT_7", request, params)
            cursor.execute(request, params)
            row = cursor.fetchone()

            return row[0] if row else 0
        

    @staticmethod
    def get_animation_id_by_verse_id(song_id, verse_id):
        with connection.cursor() as cursor:
            request = """
SELECT las.animation_id
  FROM l_animation_song_verse lasv
  JOIN l_animation_song las ON las.animation_song_id = lasv.animation_song_id
 WHERE las.animation_song_id = %s
   AND lasv.verse_id = %s
"""
            params = [song_id, verse_id]

            create_SQL_log(code_file, "Animations.get_animation_id_by_verse_id", "SELECT_8", request, params)
            cursor.execute(request, params)
            row = cursor.fetchone()

            return row[0] if row else 0
        

    def count_verses(self):
        return len(self.verses)
    

    def all_colors(self):
        with connection.cursor() as cursor:
            request = """
SELECT la.color_rgba, la.bg_rgba
  FROM l_animations la 
 WHERE la.animation_id = %s
 UNION
SELECT las.color_rgba, las.bg_rgba
  FROM l_animation_song las
 WHERE las.animation_id = %s
 UNION
SELECT lasv.color_rgba, lasv.bg_rgba
  FROM l_animation_song_verse lasv
  JOIN l_animation_song las ON las.animation_song_id = lasv.animation_song_id
 WHERE las.animation_id = %s
"""
            params = [self.animation_id, self.animation_id, self.animation_id]

            create_SQL_log(code_file, "Animations.all_colors", "SELECT_9", request, params)
            try:
                cursor.execute(request, params)
                rows = cursor.fetchall()
                self.colors = [{'color_rgba': row[0], 'bg_rgba': row[1]} for row in rows]
            except Exception as e:
                self.colors = []


###################################################
###################################################
############### BACKGROUNDS IMAGES ################
###################################################
###################################################
class BackgroundImageSubmission:
    def __init__(self, stored_path, image_id=0, original_name="", mime="", size_bytes="", width="", height="", description=""):
        self.stored_path = stored_path
        self.image_id = image_id
        self.original_name = original_name
        self.mime = mime
        self.size_bytes = size_bytes
        self.width = width
        self.height = height
        self.description = description
        self.status = None
        self.created_at = None

    def save(self):
        with connection.cursor() as cursor:
            # Try to update first
            request_update = """
UPDATE l_image_submissions
   SET original_name = %s,
       mime = %s,
       size_bytes = %s,
       width = %s,
       height = %s,
       description = %s
 WHERE stored_path = %s
"""
            params_update = [self.original_name, self.mime, self.size_bytes, self.width, self.height, self.description, self.stored_path]

            create_SQL_log(code_file, "BackgroundImageSubmission.save", "UPDATE_6", request_update, params_update)
            cursor.execute(request_update, params_update)
            if cursor.rowcount == 0:
                # If no row was updated, do an insert
                request_insert = """
INSERT INTO l_image_submissions (stored_path, original_name, mime, size_bytes, width, height, description, created_at)
     VALUES (%s, %s, %s, %s, %s, %s, %s, SYSDATE())
"""
                params_insert = [self.stored_path, self.original_name, self.mime, self.size_bytes, self.width, self.height, self.description]
                create_SQL_log(code_file, "BackgroundImageSubmission.save", "INSERT_4", request_insert, params_insert)
                try:
                    cursor.execute(request_insert, params_insert)
                    return True
                except Exception as e:
                    return False
            return True
            

    def hydrate(self):
        with connection.cursor() as cursor:
            request = """
SELECT image_id, original_name, mime, size_bytes, width, height, description, created_at
  FROM l_image_submissions
 WHERE stored_path = %s
"""
            params = [self.stored_path]

            create_SQL_log(code_file, "BackgroundImageSubmission.hydrate", "SELECT_14", request, params)
            cursor.execute(request, params)
            row = cursor.fetchone()
            if row:
                self.image_id = row[0]
                self.original_name = row[1]
                self.mime = row[2]
                self.size_bytes = row[3]
                self.width = row[4]
                self.height = row[5]
                self.description = row[6]
                self.created_at = row[7]
                

    @staticmethod
    def get_submissions():
        with connection.cursor() as cursor:
            request = """
SELECT image_id, stored_path, original_name, mime, ROUND(size_bytes / 1048576, 2) AS size_bytes, width, height, description, created_at
  FROM l_image_submissions
 ORDER BY created_at
"""
            params = []

            create_SQL_log(code_file, "BackgroundImageSubmission.get_submissions", "SELECT_11", request, params)
            cursor.execute(request, params)
            rows = cursor.fetchall()
            return [{
                    'image_id': row[0],
                    'stored_path': row[1],
                    'original_name': row[2],
                    'mime': row[3],
                    'size_bytes': row[4],
                    'width': row[5],
                    'height': row[6],
                    'aspect_ratio': round(row[5] / row[6], 2) if row[6] != 0 else None,
                    'description': row[7],
                    'created_at': row[8],
                } for row in rows]
        

    @staticmethod
    def pending_submissions_count():
        with connection.cursor() as cursor:
            request = """
SELECT COUNT(*)
  FROM l_image_submissions
"""
            params = []

            create_SQL_log(code_file, "BackgroundImageSubmission.pending_submissions_count", "SELECT_12", request, params)
            cursor.execute(request, params)
            row = cursor.fetchone()
            return row[0] if row else 0
        

    @staticmethod
    def image_exists(stored_path):
        with connection.cursor() as cursor:
            request = """
SELECT COUNT(*)
  FROM l_image_submissions
 WHERE stored_path = %s
"""
            params = [stored_path]

            create_SQL_log(code_file, "BackgroundImageSubmission.image_exists", "SELECT_13", request, params)
            cursor.execute(request, params)
            row = cursor.fetchone()
            return row[0] > 0 if row else 0
        

    @staticmethod
    def delete_by_stored_path(stored_path):
        with connection.cursor() as cursor:
            request = """
DELETE FROM l_image_submissions
      WHERE stored_path = %s
"""
            params = [stored_path]

            create_SQL_log(code_file, "BackgroundImageSubmission.delete_by_stored_path", "DELETE_3", request, params)
            cursor.execute(request, params)



class BackgroundImage:
    def __init__(self, stored_path, image_id=0, mime="", size_bytes="", width="", height="", description=""):
        self.stored_path = stored_path
        self.image_id = image_id
        self.mime = mime
        self.size_bytes = size_bytes
        self.width = width
        self.height = height
        self.description = description
        self.status = None
        self.created_at = None

    def save(self):
        with connection.cursor() as cursor:
            # Try to update first
            request_update = """
UPDATE l_image_backgrounds
   SET mime = %s,
       size_bytes = %s,
       width = %s,
       height = %s,
       description = %s,
       status = %s
 WHERE stored_path = %s
"""
            params_update = [self.mime, self.size_bytes, self.width, self.height, self.description, self.status, self.stored_path]

            create_SQL_log(code_file, "BackgroundImage.save", "UPDATE_7", request_update, params_update)
            cursor.execute(request_update, params_update)
            if cursor.rowcount == 0:
                # If no row was updated, do an insert
                request_insert = """
INSERT INTO l_image_backgrounds (stored_path, mime, size_bytes, width, height, description, created_at)
     VALUES (%s, %s, %s, %s, %s, %s, SYSDATE())
"""
                params_insert = [self.stored_path, self.mime, self.size_bytes, self.width, self.height, self.description]
                create_SQL_log(code_file, "BackgroundImage.save", "INSERT_5", request_insert, params_insert)
                try:
                    cursor.execute(request_insert, params_insert)
                    return True
                except Exception as e:
                    return False
            return True
            

    def hydrate(self):
        with connection.cursor() as cursor:
            request = """
SELECT image_id, mime, size_bytes, width, height, description, created_at, status
  FROM l_image_backgrounds
 WHERE stored_path = %s
"""
            params = [self.stored_path]

            create_SQL_log(code_file, "BackgroundImage.hydrate", "SELECT_16", request, params)
            cursor.execute(request, params)
            row = cursor.fetchone()
            if row:
                self.image_id = row[0]
                self.mime = row[1]
                self.size_bytes = row[2]
                self.width = row[3]
                self.height = row[4]
                self.description = row[5]
                self.created_at = row[6]
                self.status = row[7]

    @staticmethod
    def get_backgrounds(status_filter=None):
        if status_filter is not None:
            status = f"""
   AND status = '{status_filter}'"""
        else:
            status = ""

        with connection.cursor() as cursor:
            request = f"""
SELECT image_id, stored_path, mime, ROUND(size_bytes / 1048576, 2) AS size_bytes, width, height, description, created_at, status
  FROM l_image_backgrounds
 WHERE 1 = 1{status}
 ORDER BY status, created_at DESC
"""
            params = []

            create_SQL_log(code_file, "BackgroundImage.get_backgrounds", "SELECT_15", request, params)
            cursor.execute(request, params)
            rows = cursor.fetchall()
            return [{
                    'image_id': row[0],
                    'stored_path': row[1],
                    'mime': row[2],
                    'size_bytes': row[3],
                    'width': row[4],
                    'height': row[5],
                    'aspect_ratio': round(row[4] / row[5], 2) if row[5] != 0 else None,
                    'description': row[6],
                    'created_at': row[7],
                    'status': row[8],
                } for row in rows]
        

    @staticmethod
    def pending_submissions_count():
        with connection.cursor() as cursor:
            request = """
SELECT COUNT(*)
  FROM l_image_backgrounds
"""
            params = []

            create_SQL_log(code_file, "BackgroundImage.pending_submissions_count", "SELECT_17", request, params)
            cursor.execute(request, params)
            row = cursor.fetchone()
            return row[0] if row else 0
        

    @staticmethod
    def image_exists(stored_path):
        with connection.cursor() as cursor:
            request = """
SELECT COUNT(*)
  FROM l_image_backgrounds
 WHERE stored_path = %s
"""
            params = [stored_path]

            create_SQL_log(code_file, "BackgroundImage.image_exists", "SELECT_18", request, params)
            cursor.execute(request, params)
            row = cursor.fetchone()
            return row[0] > 0 if row else 0
        

    @staticmethod
    def delete_by_stored_path(stored_path):
        with connection.cursor() as cursor:
            request = """
DELETE FROM l_image_backgrounds
      WHERE stored_path = %s
"""
            params = [stored_path]
            
            create_SQL_log(code_file, "BackgroundImage.delete_by_stored_path", "DELETE_4", request, params)
            cursor.execute(request, params)