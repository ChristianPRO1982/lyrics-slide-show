from django.db import models


class SiteParams(models.Model):
    language = models.CharField(max_length=2, primary_key=True)
    title = models.CharField(max_length=100)
    title_h1 = models.CharField(max_length=255)
    home_text = models.TextField()
    bloc1_text = models.TextField()
    bloc2_text = models.TextField()
    verse_max_lines = models.IntegerField()
    verse_max_characters_for_a_line = models.IntegerField()
    chorus_prefix = models.CharField(max_length=10)
    verse_prefix1 = models.CharField(max_length=10)
    verse_prefix2 = models.CharField(max_length=3)
    admin_message = models.TextField()
    moderator_message = models.TextField()
    bg_img_max_bytes = models.IntegerField(default=2097152)
    bg_img_min_w = models.IntegerField(default=800)
    bg_img_min_h = models.IntegerField(default=600)
    bg_img_max_w = models.IntegerField(default=4096)
    bg_img_max_h = models.IntegerField(default=3072)
    bg_img_ratio_min = models.DecimalField(max_digits=3, decimal_places=1, default=1.3)
    bg_img_ratio_max = models.DecimalField(max_digits=3, decimal_places=1, default=2.0)
    bg_img_allowed_ext = models.CharField(max_length=100, default=".jpg,.jpeg,.png")
    bg_img_allowed_mime = models.CharField(max_length=100, default="image/jpeg,image/png")

    class Meta:
        db_table = 'lss"."site_params'


class DirectoryUserRecord(models.Model):
    id = models.UUIDField(primary_key=True)
    username = models.CharField(max_length=255, null=True, blank=True)
    first_name = models.CharField(max_length=255, null=True, blank=True)
    last_name = models.CharField(max_length=255, null=True, blank=True)
    email = models.CharField(max_length=255, null=True, blank=True)
    enabled = models.BooleanField(default=True)
    email_verified = models.BooleanField(default=False)
    synced_at = models.TimeField(null=True, blank=True)
    last_login_at = models.TimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'users"."users'
