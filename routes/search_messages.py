from fastapi import APIRouter, Depends, HTTPException, status
from models.schemas import SearchFilters, MessageCreate
from database import get_supabase_admin
from middleware.auth import get_current_user
from config import settings
from datetime import datetime
import uuid

# ── Search Router ─────────────────────────────────────────────────────────────

search_router = APIRouter(prefix="/search", tags=["Search"])


@search_router.post("/", response_model=dict)
async def search_items(filters: SearchFilters):
    db = get_supabase_admin()
    offset = (filters.page - 1) * filters.limit
    results = {"lost_items": [], "found_items": [], "total": 0}

    def apply_filters(query, item_type: str):
        if filters.location:
            query = query.eq("location", filters.location)
        if filters.category:
            query = query.eq("category", filters.category)
        if filters.status:
            query = query.eq("status", filters.status.value)
        if filters.date_from:
            date_field = "date_lost" if item_type == "lost" else "date_found"
            query = query.gte(date_field, filters.date_from.isoformat())
        if filters.date_to:
            date_field = "date_lost" if item_type == "lost" else "date_found"
            query = query.lte(date_field, filters.date_to.isoformat())
        if filters.query:
            # Full-text search on item_name and description
            q = filters.query.lower()
            query = query.or_(
                f"item_name.ilike.%{q}%,description.ilike.%{q}%"
            )
        return query

    item_type = filters.item_type or "all"

    if item_type in ("lost", "all"):
        q = db.table("lost_items").select("*", count="exact").order("created_at", desc=True)
        q = apply_filters(q, "lost")
        res = q.range(offset, offset + filters.limit - 1).execute()
        results["lost_items"] = res.data or []
        results["lost_count"] = res.count or 0

    if item_type in ("found", "all"):
        q = db.table("found_items").select("*", count="exact").order("created_at", desc=True)
        q = apply_filters(q, "found")
        res = q.range(offset, offset + filters.limit - 1).execute()
        results["found_items"] = res.data or []
        results["found_count"] = res.count or 0

    results["total"] = results.get("lost_count", 0) + results.get("found_count", 0)
    results["page"] = filters.page
    results["limit"] = filters.limit

    return results


@search_router.get("/locations")
async def get_campus_locations():
    return {"locations": settings.CAMPUS_LOCATIONS}


@search_router.get("/categories")
async def get_item_categories():
    return {"categories": settings.ITEM_CATEGORIES}


# ── Messages Router ───────────────────────────────────────────────────────────

messages_router = APIRouter(prefix="/messages", tags=["Messages"])


@messages_router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
async def send_message(
    msg_data: MessageCreate,
    current_user: dict = Depends(get_current_user),
):
    db = get_supabase_admin()

    if msg_data.receiver_id == current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot send message to yourself",
        )

    record = {
        "id": str(uuid.uuid4()),
        "sender_id": current_user["id"],
        "receiver_id": msg_data.receiver_id,
        "item_id": msg_data.item_id,
        "item_type": msg_data.item_type,
        "content": msg_data.content,
        "is_read": False,
        "created_at": datetime.utcnow().isoformat(),
    }

    result = db.table("messages").insert(record).execute()
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send message",
        )

    return {"message": result.data[0], "status": "sent"}


@messages_router.get("/inbox", response_model=list)
async def get_inbox(current_user: dict = Depends(get_current_user)):
    db = get_supabase_admin()
    result = (
        db.table("messages")
        .select("*")
        .eq("receiver_id", current_user["id"])
        .order("created_at", desc=True)
        .execute()
    )
    messages = result.data or []

    # Enrich with sender info
    for msg in messages:
        sender = (
            db.table("users")
            .select("id, full_name, email")
            .eq("id", msg["sender_id"])
            .single()
            .execute()
        )
        msg["sender"] = sender.data

    return messages


@messages_router.get("/sent", response_model=list)
async def get_sent(current_user: dict = Depends(get_current_user)):
    db = get_supabase_admin()
    result = (
        db.table("messages")
        .select("*")
        .eq("sender_id", current_user["id"])
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


@messages_router.get("/thread/{item_id}/{item_type}", response_model=list)
async def get_thread(
    item_id: str,
    item_type: str,
    current_user: dict = Depends(get_current_user),
):
    db = get_supabase_admin()
    uid = current_user["id"]
    result = (
        db.table("messages")
        .select("*")
        .eq("item_id", item_id)
        .eq("item_type", item_type)
        .or_(f"sender_id.eq.{uid},receiver_id.eq.{uid}")
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


@messages_router.put("/{message_id}/read")
async def mark_read(
    message_id: str,
    current_user: dict = Depends(get_current_user),
):
    db = get_supabase_admin()
    db.table("messages").update({"is_read": True}).eq("id", message_id).eq(
        "receiver_id", current_user["id"]
    ).execute()
    return {"status": "marked as read"}


@messages_router.get("/unread-count")
async def unread_count(current_user: dict = Depends(get_current_user)):
    db = get_supabase_admin()
    result = (
        db.table("messages")
        .select("id", count="exact")
        .eq("receiver_id", current_user["id"])
        .eq("is_read", False)
        .execute()
    )
    return {"count": result.count or 0}
