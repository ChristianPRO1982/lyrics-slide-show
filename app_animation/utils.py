from __future__ import annotations

from typing import Any

from django.core.files.uploadedfile import UploadedFile


def _open_image(upload: UploadedFile) -> tuple[int, int, str]:
    try:
        from PIL import Image
    except Exception:
        fmt = "JPEG" if (upload.content_type or "").lower() == "image/jpeg" else "PNG"
        return 0, 0, fmt

    try:
        try:
            position = upload.tell()
        except Exception:
            position = None

        image = Image.open(upload)
        image.verify()
        upload.seek(0)
        image = Image.open(upload)
        width, height = image.size
        fmt = str(image.format or "").upper()
        return width, height, fmt
    except Exception:
        return 0, 0, ""
    finally:
        try:
            if position is not None:
                upload.seek(position)
        except Exception:
            pass


def validate_image(upload: UploadedFile, cfg: dict[str, Any]) -> str:
    name = str(upload.name or "").lower()
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
        return "too_large"

    if allowed_ext and not any(name.endswith(ext) for ext in allowed_ext):
        return "invalid_extension"

    if allowed_mime and str(upload.content_type or "").lower() not in allowed_mime:
        return "invalid_mime"

    width, height, fmt = _open_image(upload)
    if not fmt:
        return "invalid_image"

    if width and height:
        if width < min_w or height < min_h:
            return "too_small"
        if width > max_w or height > max_h:
            return "too_large_dimensions"
        ratio = float(width) / float(height)
        if ratio < ratio_min or ratio > ratio_max:
            return "invalid_ratio"
    return ""
