from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, Form
from typing import Optional
from datetime import date, datetime
import uuid

from models.schemas import LostItemCreate, LostItemUpdate, LostItem, ItemStatus
from database import get_supabase_admin
from middleware.auth import get_current_user
from services.matching import find_matches
from services.image_upload import upload_image

router = APIRouter(prefix="/lost-items", tags=["Lost Items"])


def _enrich_item(item: dict, db) -> dict:
    """Attach poster profile to item dict."""
    if item.get("user_id"):
        user_result = (
            db.table("users")
            .select("id, full_name, email, department, student_id")
            .eq("id", item["user_id"])
            .single()
            .execute()
        )
        item["poster"] = user_result.data if user_result.data else None
    return item


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_lost_item(
    item_data: LostItemCreate,
    current_user: dict = Depends(get_current_user),
):
    db = get_supabase_admin()

    record = {
        "id": str(uuid.uuid4()),
        "user_id": current_user["id"],
        "item_name": item_data.item_name,
        "description": item_data.description,
        "location": item_data.location,
        "date_lost": item_data.date_lost.isoformat(),
        "category": item_data.category,
        "contact_info": item_data.contact_info,
        "image_url": item_data.image_url,
        "status": ItemStatus.LOST.value,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }

    result = db.table("lost_items").insert(record).execute()
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create lost item",
        )

    created_item = result.data[0]

    # Run matching in background
    matches = await find_matches(created_item)

    return {
        "item": _enrich_item(created_item, db),
        "matches": matches,
        "message": f"Lost item reported. {len(matches)} potential match(es) found.",
    }


@router.get("/", response_model=list)
async def list_lost_items(
    page: int = 1,
    limit: int = 20,
    status: Optional[str] = None,
    location: Optional[str] = None,
    category: Optional[str] = None,
):
    db = get_supabase_admin()
    offset = (page - 1) * limit

    query = db.table("lost_items").select("*").order("created_at", desc=True)

    if status:
        query = query.eq("status", status)
    if location:
        query = query.eq("location", location)
    if category:
        query = query.eq("category", category)

    result = query.range(offset, offset + limit - 1).execute()
    items = result.data or []
    return [_enrich_item(item, db) for item in items]


@router.get("/my", response_model=list)
async def my_lost_items(current_user: dict = Depends(get_current_user)):
    db = get_supabase_admin()
    result = (
        db.table("lost_items")
        .select("*")
        .eq("user_id", current_user["id"])
        .order("created_at", desc=True)
        .execute()
    )
    return [_enrich_item(item, db) for item in (result.data or [])]


@router.get("/{item_id}", response_model=dict)
async def get_lost_item(item_id: str):
    db = get_supabase_admin()
    result = db.table("lost_items").select("*").eq("id", item_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return _enrich_item(result.data, db)


@router.put("/{item_id}", response_model=dict)
async def update_lost_item(
    item_id: str,
    update_data: LostItemUpdate,
    current_user: dict = Depends(get_current_user),
):
    db = get_supabase_admin()

    # Ownership check
    existing = db.table("lost_items").select("user_id").eq("id", item_id).single().execute()
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    if existing.data["user_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your item")

    update_dict = update_data.model_dump(exclude_none=True)
    if "date_lost" in update_dict:
        update_dict["date_lost"] = update_dict["date_lost"].isoformat()
    update_dict["updated_at"] = datetime.utcnow().isoformat()

    result = db.table("lost_items").update(update_dict).eq("id", item_id).execute()
    return _enrich_item(result.data[0], db)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lost_item(
    item_id: str,
    current_user: dict = Depends(get_current_user),
):
    db = get_supabase_admin()
    existing = db.table("lost_items").select("user_id").eq("id", item_id).single().execute()
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    if existing.data["user_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your item")
    db.table("lost_items").delete().eq("id", item_id).execute()


@router.post("/{item_id}/upload-image")
async def upload_lost_item_image(
    item_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    db = get_supabase_admin()
    existing = db.table("lost_items").select("user_id").eq("id", item_id).single().execute()
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    if existing.data["user_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your item")

    image_url = await upload_image(file, bucket="item-images", folder="lost")
    db.table("lost_items").update({"image_url": image_url}).eq("id", item_id).execute()
    return {"image_url": image_url}


@router.get("/{item_id}/matches", response_model=list)
async def get_matches_for_lost_item(item_id: str):
    db = get_supabase_admin()
    result = db.table("lost_items").select("*").eq("id", item_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return await find_matches(result.data)
