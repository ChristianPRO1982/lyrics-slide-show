from django.contrib import admin

from .models import Animation, AnimationSong, AnimationVerseOverride


@admin.register(Animation)
class AnimationAdmin(admin.ModelAdmin):
    list_display = ("animation_id", "title", "group", "scheduled_at")
    list_filter = ("group",)
    search_fields = ("title", "description")


@admin.register(AnimationSong)
class AnimationSongAdmin(admin.ModelAdmin):
    list_display = ("animation_song_id", "animation", "song", "position")
    list_filter = ("animation",)


@admin.register(AnimationVerseOverride)
class AnimationVerseOverrideAdmin(admin.ModelAdmin):
    list_display = ("animation_song", "source_verse_id", "is_visible")
    list_filter = ("is_visible",)
