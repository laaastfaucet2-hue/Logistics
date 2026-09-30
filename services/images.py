"""Validate and normalize uploaded official images before replacing anything."""
import io
import secrets
from PIL import Image, ImageOps, UnidentifiedImageError
from data_access import dataguard


def png_bytes(source, max_size=(1000, 1000)):
    try:
        with Image.open(source) as image:
            if image.width * image.height > 24_000_000:
                raise ValueError("الصورة كبيرة جدًا؛ الحد ٢٤ مليون بكسل")
            image = ImageOps.exif_transpose(image).convert("RGBA")
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
            out = io.BytesIO()
            image.save(out, format="PNG")
            return out.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("ملف الصورة غير صالح؛ استخدم PNG أو JPG أو WEBP") from exc


def save_logo(source, folder):
    content = png_bytes(source)
    name = f"logo-{secrets.token_hex(8)}.png"
    dataguard.atomic_save(lambda path: __import__('pathlib').Path(path).write_bytes(content),
                          folder / name, zip_check=False)
    return name
