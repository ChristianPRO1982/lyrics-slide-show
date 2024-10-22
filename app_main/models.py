from django.db import models



class Song(models.Model):
    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255, unique=True, blank=False, null=False)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.title