# app_animation/utils.py
from __future__ import annotations
from typing import Dict, Tuple
from django.core.files.uploadedfile import UploadedFile
from django.utils.translation import gettext as _

def _open_image(upload: UploadedFile) -> Tuple[int, int, str]:
    try:
        from PIL import Image
    except Exception:
        fmt = "JPEG" if (upload.content_type or "").lower() == "image/jpeg" else "PNG"
        return 0, 0, fmt
    try:
        try:
            pos = upload.tell()
        except Exception:
            pos = None
        img = Image.open(upload)
        img.verify()
        upload.seek(0)
        img = Image.open(upload)
        w, h = img.size
        fmt = (img.format or "").upper()
        return w, h, fmt
    except Exception:
        return 0, 0, ""
    finally:
        try:
            if pos is not None:
                upload.seek(pos)
        except Exception:
            pass

def validate_image(upload: UploadedFile, cfg: Dict[str, object]) -> str:
    name = (upload.name or "").lower()
    allowed_ext = set(cfg.get("allowed_ext", []))
    allowed_mime = set(cfg.get("allowed_mime", []))
    max_bytes = int(cfg.get("max_bytes", 2 * 1024 * 1024))
    min_w = int(cfg.get("min_w", 800))
    min_h = int(cfg.get("min_h", 600))
    max_w = int(cfg.get("max_w", 4096))
    max_h = int(cfg.get("max_h", 3072))
    ratio_min = float(cfg.get("ratio_min", 1.3))
    ratio_max = float(cfg.get("ratio_max", 2.0))

    if int(getattr(upload, "size", 0)) > max_bytes:
        mb = max_bytes / (1024 * 1024)
        return "[ERR53]"

    if allowed_ext and not any(name.endswith(ext) for ext in allowed_ext):
        return "[ERR54]"
    if allowed_mime and (upload.content_type or "").lower() not in allowed_mime:
        return "[ERR55]"

    w, h, fmt = _open_image(upload)
    if not fmt:
        return "[ERR56]"

    if w and h:
        if w < min_w or h < min_h:
            return "[ERR57]"
        if w > max_w or h > max_h:
            return "[ERR58]"
        ratio = float(w) / float(h)
        if ratio < ratio_min or ratio > ratio_max:
            return "[ERR59]"
    return ""


def all_lyrics(slides):
    try:
        new_slides = []
        verses_choruses = []
        for slide in slides:
            if slide['new_animation_song'] and verses_choruses != []:
                new_slides.extend(lyrics(verses_choruses))
                verses_choruses = []
            
            verses_choruses.append(slide)
        new_slides.extend(lyrics(verses_choruses))

        return new_slides

    except Exception as e:
        return None
    

def lyrics(slides):
    try:
        choruses = []
        lyrics = []

        # Get all choruses
        for slide in slides:
            if slide['chorus'] == 1:
                slide['new_animation_song'] = 0
                choruses.append(slide)
        
        # get all slides : choruses + verses
        start_by_chorus = True
        for slide in slides:
            if slide['chorus'] != 1:
                if slide['text']:
                    slide['new_animation_song'] = 0
                    lyrics.append(slide)
                if slide['followed'] == 0 and len(choruses) > 0 and slide['chorus'] != 3:
                    lyrics.extend([chorus.copy() for chorus in choruses])
            elif start_by_chorus:
                lyrics.extend([chorus.copy() for chorus in choruses])
            start_by_chorus = False
        
        lyrics[0]['new_animation_song'] = 1
        return lyrics

    except Exception as e:
        return []