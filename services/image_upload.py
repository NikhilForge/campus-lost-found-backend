from fastapi import UploadFile, HTTPException, status
from database import get_supabase_admin
from config import settings
import uuid
import io
from PIL import Image


ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
MAX_DIMENSION = 1920  # px


async def upload_image(
    file: UploadFile,
    bucket: str = "item-images",
    folder: str = "misc",
) -> str:
    """
    Validates, resizes (if needed), and uploads an image to Supabase Storage.
    Returns the public URL of the uploaded image.
    """

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {file.content_type}. Allowed: JPEG, PNG, WEBP, GIF",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds 5 MB limit",
        )

    # Resize if needed
    try:
        img = Image.open(io.BytesIO(content))
        if max(img.size) > MAX_DIMENSION:
            img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)
            buffer = io.BytesIO()
            fmt = img.format or "JPEG"
            img.save(buffer, format=fmt)
            content = buffer.getvalue()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image file: {str(e)}",
        )

    ext = file.content_type.split("/")[-1]
    filename = f"{folder}/{uuid.uuid4()}.{ext}"

    db = get_supabase_admin()
    try:
        db.storage.from_(bucket).upload(
            filename,
            content,
            {"content-type": file.content_type, "upsert": "true"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Image upload failed: {str(e)}",
        )

    public_url = db.storage.from_(bucket).get_public_url(filename)
    return public_url
