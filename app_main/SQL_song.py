from django.db import connection



############
### SONG ###
############
class Song:
    def __init__(self, song_id=None, title=None, sub_title=None, description=None):
        self.song_id = song_id
        self.title = title
        self.sub_title = sub_title
        self.description = description

    @staticmethod
    def get_all_songs():
        request = """
  SELECT *
    FROM l_songs
ORDER BY title, sub_title
"""

        print("", request, "")
        with connection.cursor() as cursor:
            cursor.execute(request)
            rows = cursor.fetchall()
        return [{'id': row[0], 'title': row[1], 'sub_title': row[2], 'description': row[3]} for row in rows]

    @classmethod
    def get_song_by_id(cls, song_id):
        with connection.cursor() as cursor:
            request = f"""
SELECT *
  FROM l_songs
 WHERE song_id = {song_id}
"""
            
            print("", request, "")
            cursor.execute(request)
            row = cursor.fetchone()
        if row:
            return cls(song_id=row[0], title=row[1], sub_title=row[2], description=row[3])
        return None

    def save(self):
        with connection.cursor() as cursor:
            if self.song_id:
                request = f"""
UPDATE l_songs
   SET title = "{self.title}",
       sub_title = "{self.sub_title}",
       description = "{self.description}"
 WHERE song_id = {self.song_id}"""
                
                print("", request, "")
                cursor.execute(
                    request
                )
            else:
                request = f"""
INSERT INTO l_songs (title, sub_title, description)
     VALUES ("{self.title}", "{self.sub_title}", "{self.description}")"""
                
                print("", request, "")
                cursor.execute(
                    request
                )
                self.song_id = cursor.lastrowid

    def delete(self):
        if not self.song_id:
            raise ValueError("L'ID du chant est requis pour le supprimer.")
        with connection.cursor() as cursor:
            request = f"""
DELETE FROM l_songs
      WHERE song_id = {self.song_id}"""

            print("", request, "")
            cursor.execute(request)

    def get_verses(self):
        return Verse.get_verses_by_song_id(self.song_id)


####################
### CHORUS/VERSE ###
####################
class Verse:
    def __init__(self, verse_id=None, song_id=None, num=None, num_verse=None, chorus=False, followed=False, text=""):
        self.verse_id = verse_id
        self.song_id = song_id
        self.num = num
        self.num_verse = num_verse
        self.chorus = chorus
        self.followed = followed
        self.text = text

    @staticmethod
    def get_verses_by_song_id(song_id):
        """Récupère tous les couplets/refrains d'une chanson spécifique."""
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT verse_id, num, num_verse, chorus, followed, text FROM l_verses WHERE song_id = %s ORDER BY num",
                [song_id]
            )
            rows = cursor.fetchall()
        return [Verse(verse_id=row[0], song_id=song_id, num=row[1], num_verse=row[2], chorus=row[3], followed=row[4], text=row[5]) for row in rows]

    def save(self):
        """Ajoute ou met à jour un couplet/refrain."""
        with connection.cursor() as cursor:
            if self.verse_id:
                cursor.execute(
                    "UPDATE l_verses SET num = %s, num_verse = %s, chorus = %s, followed = %s, text = %s WHERE verse_id = %s",
                    [self.num, self.num_verse, self.chorus, self.followed, self.text, self.verse_id]
                )
            else:
                cursor.execute(
                    "INSERT INTO l_verses (song_id, num, num_verse, chorus, followed, text) VALUES (%s, %s, %s, %s, %s, %s)",
                    [self.song_id, self.num, self.num_verse, self.chorus, self.followed, self.text]
                )
                self.verse_id = cursor.lastrowid

    def delete(self):
        """Supprime le couplet/refrain."""
        if not self.verse_id:
            raise ValueError("L'ID du couplet est requis pour le supprimer.")
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM l_verses WHERE verse_id = %s", [self.verse_id])
