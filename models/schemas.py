from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import date, datetime
from enum import Enum


# ── Enums ─────────────────────────────────────────────────────────────────────

class ItemStatus(str, Enum):
    LOST = "lost"
    FOUND = "found"
    RETURNED = "returned"
    CLOSED = "closed"


# ── Auth ──────────────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=2, max_length=100)
    student_id: str = Field(..., min_length=3, max_length=20)
    department: str = Field(..., min_length=2, max_length=100)
    phone: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserProfile(BaseModel):
    id: str
    email: str
    full_name: str
    student_id: str
    department: str
    phone: Optional[str] = None
    created_at: Optional[datetime] = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfile


# ── Lost Items ────────────────────────────────────────────────────────────────

class LostItemCreate(BaseModel):
    item_name: str = Field(..., min_length=2, max_length=100)
    description: str = Field(..., min_length=10, max_length=1000)
    location: str
    date_lost: date
    category: str
    contact_info: str = Field(..., min_length=5, max_length=200)
    image_url: Optional[str] = None


class LostItemUpdate(BaseModel):
    item_name: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    date_lost: Optional[date] = None
    category: Optional[str] = None
    contact_info: Optional[str] = None
    image_url: Optional[str] = None
    status: Optional[ItemStatus] = None


class LostItem(BaseModel):
    id: str
    user_id: str
    item_name: str
    description: str
    location: str
    date_lost: date
    category: str
    contact_info: str
    image_url: Optional[str] = None
    status: ItemStatus = ItemStatus.LOST
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    poster: Optional[dict] = None


# ── Found Items ───────────────────────────────────────────────────────────────

class FoundItemCreate(BaseModel):
    item_name: str = Field(..., min_length=2, max_length=100)
    description: str = Field(..., min_length=10, max_length=1000)
    location: str
    date_found: date
    category: str
    image_url: Optional[str] = None
    storage_location: Optional[str] = Field(
        None, description="Where the item is currently kept"
    )


class FoundItemUpdate(BaseModel):
    item_name: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    date_found: Optional[date] = None
    category: Optional[str] = None
    image_url: Optional[str] = None
    storage_location: Optional[str] = None
    status: Optional[ItemStatus] = None


class FoundItem(BaseModel):
    id: str
    user_id: str
    item_name: str
    description: str
    location: str
    date_found: date
    category: str
    image_url: Optional[str] = None
    storage_location: Optional[str] = None
    status: ItemStatus = ItemStatus.FOUND
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    poster: Optional[dict] = None


# ── Messages ──────────────────────────────────────────────────────────────────

class MessageCreate(BaseModel):
    receiver_id: str
    item_id: str
    item_type: str = Field(..., pattern="^(lost|found)$")
    content: str = Field(..., min_length=1, max_length=1000)


class Message(BaseModel):
    id: str
    sender_id: str
    receiver_id: str
    item_id: str
    item_type: str
    content: str
    is_read: bool = False
    created_at: Optional[datetime] = None
    sender: Optional[dict] = None


# ── Search ────────────────────────────────────────────────────────────────────

class SearchFilters(BaseModel):
    query: Optional[str] = None
    location: Optional[str] = None
    category: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    status: Optional[ItemStatus] = None
    item_type: Optional[str] = Field(None, pattern="^(lost|found|all)$")
    page: int = Field(1, ge=1)
    limit: int = Field(20, ge=1, le=100)


# ── Matching ──────────────────────────────────────────────────────────────────

class MatchResult(BaseModel):
    found_item: FoundItem
    match_score: float
    match_reasons: list[str]
