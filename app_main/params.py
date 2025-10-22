# app_animation/params.py
from __future__ import annotations
from typing import Dict, Any, List
from django.utils.translation import get_language
from app_main.SQL_main import Site

def _split_csv(value: str) -> List[str]:
    return [s.strip().lower() for s in str(value or "").split(",") if s.strip()]

def get_image_params(request) -> Dict[str, Any]:
    lang = getattr(request, "LANGUAGE_CODE", None) or get_language() or "fr"
    site = Site(lang)
    return {
        "max_bytes": int(site.bg_img_max_bytes),
        "min_w": int(site.bg_img_min_w),
        "min_h": int(site.bg_img_min_h),
        "max_w": int(site.bg_img_max_w),
        "max_h": int(site.bg_img_max_h),
        "ratio_min": float(site.bg_img_ratio_min),
        "ratio_max": float(site.bg_img_ratio_max),
        "allowed_ext": _split_csv(site.bg_img_allowed_ext),
        "allowed_mime": _split_csv(site.bg_img_allowed_mime),
    }
