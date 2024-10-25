from django.db import models



class Song(models.Model):
    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255, unique=True, blank=False, null=False)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.title
    

class Verse(models.Model):
    id = models.AutoField(primary_key=True)
    song = models.ForeignKey(Song, on_delete=models.CASCADE, related_name='verses')
    num = models.IntegerField()
    num_verse = models.IntegerField()
    chorus = models.BooleanField()
    followed = models.BooleanField()
    text = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Verse {self.num} - {'Chorus' if self.chorus else 'Verse'}"
