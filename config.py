from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    SECRET_KEY: str = "changeme-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days

    APP_NAME: str = "Campus Lost & Found API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    ALLOWED_ORIGINS: str = "*"

    CAMPUS_LOCATIONS: List[str] = [
        "Library",
        "Cafeteria",
        "Classroom Block A",
        "Classroom Block B",
        "Classroom Block C",
        "Laboratory - CS",
        "Laboratory - Science",
        "Playground",
        "Parking Area",
        "Hostel Block 1",
        "Hostel Block 2",
        "Administrative Block",
        "Sports Complex",
        "Auditorium",
        "Campus Entrance",
    ]

    ITEM_CATEGORIES: List[str] = [
        "Electronics",
        "Books & Stationery",
        "Clothing & Accessories",
        "ID Cards & Documents",
        "Keys",
        "Bags & Wallets",
        "Jewelry",
        "Sports Equipment",
        "Musical Instruments",
        "Other",
    ]

    class Config:
        env_file = ".env"


settings = Settings()
