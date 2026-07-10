"""
=============================================================================
SmartKrishi - Database Models
SQLAlchemy ORM models for farmer profiles, chat history, and more
=============================================================================
"""

from datetime import datetime, timezone
from typing import Optional
import json

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


def utcnow():
    return datetime.now(timezone.utc)


# =============================================================================
# FARMER / USER MODEL
# =============================================================================
class Farmer(UserMixin, db.Model):
    """Farmer user profile and authentication."""
    __tablename__ = "farmers"

    id = db.Column(db.Integer, primary_key=True)
    # Auth
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=True, index=True)
    phone = db.Column(db.String(15), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    # Profile
    full_name = db.Column(db.String(120), nullable=False)
    profile_image = db.Column(db.String(255), nullable=True)
    # Location
    state = db.Column(db.String(60), nullable=True)
    district = db.Column(db.String(60), nullable=True)
    village = db.Column(db.String(60), nullable=True)
    pincode = db.Column(db.String(10), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    # Farm Details
    farm_size = db.Column(db.Float, nullable=True)  # in acres
    soil_type = db.Column(db.String(50), nullable=True)
    irrigation_type = db.Column(db.String(50), nullable=True)
    # JSON fields for arrays
    _crops_json = db.Column("crops", db.Text, nullable=True)
    # Preferences
    preferred_language = db.Column(db.String(10), default="en")
    dark_mode = db.Column(db.Boolean, default=False)
    voice_enabled = db.Column(db.Boolean, default=True)
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    last_login = db.Column(db.DateTime(timezone=True), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    # Relationships
    chat_sessions = db.relationship("ChatSession", back_populates="farmer", cascade="all, delete-orphan")
    soil_analyses = db.relationship("SoilAnalysis", back_populates="farmer", cascade="all, delete-orphan")
    weather_alerts = db.relationship("WeatherAlert", back_populates="farmer", cascade="all, delete-orphan")

    @property
    def crops(self):
        if self._crops_json:
            return json.loads(self._crops_json)
        return []

    @crops.setter
    def crops(self, value):
        self._crops_json = json.dumps(value) if value else "[]"

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def to_profile_dict(self) -> dict:
        """Return profile data for agent personalization."""
        return {
            "name": self.full_name,
            "state": self.state,
            "district": self.district,
            "farm_size": self.farm_size,
            "crops": self.crops,
            "soil_type": self.soil_type,
            "irrigation": self.irrigation_type,
            "language": self.preferred_language,
        }

    def to_public_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "full_name": self.full_name,
            "state": self.state,
            "district": self.district,
            "farm_size": self.farm_size,
            "crops": self.crops,
            "soil_type": self.soil_type,
            "preferred_language": self.preferred_language,
        }

    def __repr__(self):
        return f"<Farmer {self.username}>"


# =============================================================================
# CHAT MODELS
# =============================================================================
class ChatSession(db.Model):
    """A conversation session between a farmer and the AI advisor."""
    __tablename__ = "chat_sessions"

    id = db.Column(db.Integer, primary_key=True)
    farmer_id = db.Column(db.Integer, db.ForeignKey("farmers.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=True)
    language = db.Column(db.String(10), default="en")
    context_type = db.Column(db.String(50), nullable=True)  # general, disease, weather, scheme
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    is_archived = db.Column(db.Boolean, default=False)

    # Relationships
    farmer = db.relationship("Farmer", back_populates="chat_sessions")
    messages = db.relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.timestamp")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title or f"Chat #{self.id}",
            "language": self.language,
            "context_type": self.context_type,
            "created_at": self.created_at.isoformat(),
            "message_count": len(self.messages),
        }


class ChatMessage(db.Model):
    """Individual message in a chat session."""
    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("chat_sessions.id"), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)  # user, assistant
    content = db.Column(db.Text, nullable=False)
    language = db.Column(db.String(10), default="en")
    # Metadata
    rag_context_used = db.Column(db.Boolean, default=False)
    rag_docs_retrieved = db.Column(db.Integer, default=0)
    model_used = db.Column(db.String(100), nullable=True)
    tokens_used = db.Column(db.Integer, nullable=True)
    response_time_ms = db.Column(db.Integer, nullable=True)
    # Voice
    is_voice_input = db.Column(db.Boolean, default=False)
    audio_url = db.Column(db.String(255), nullable=True)
    # Timestamps
    timestamp = db.Column(db.DateTime(timezone=True), default=utcnow, index=True)

    session = db.relationship("ChatSession", back_populates="messages")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "language": self.language,
            "rag_context_used": self.rag_context_used,
            "timestamp": self.timestamp.isoformat(),
            "is_voice": self.is_voice_input,
        }


# =============================================================================
# SOIL ANALYSIS
# =============================================================================
class SoilAnalysis(db.Model):
    """Soil test results stored for a farmer's field."""
    __tablename__ = "soil_analyses"

    id = db.Column(db.Integer, primary_key=True)
    farmer_id = db.Column(db.Integer, db.ForeignKey("farmers.id"), nullable=False, index=True)
    field_name = db.Column(db.String(100), nullable=True)
    # Soil Parameters
    ph = db.Column(db.Float, nullable=True)
    nitrogen_kg_ha = db.Column(db.Float, nullable=True)
    phosphorus_kg_ha = db.Column(db.Float, nullable=True)
    potassium_kg_ha = db.Column(db.Float, nullable=True)
    organic_carbon_pct = db.Column(db.Float, nullable=True)
    sulphur_ppm = db.Column(db.Float, nullable=True)
    zinc_ppm = db.Column(db.Float, nullable=True)
    boron_ppm = db.Column(db.Float, nullable=True)
    iron_ppm = db.Column(db.Float, nullable=True)
    manganese_ppm = db.Column(db.Float, nullable=True)
    # AI Recommendations
    ai_recommendations = db.Column(db.Text, nullable=True)
    recommended_crops = db.Column(db.Text, nullable=True)  # JSON
    # Meta
    test_date = db.Column(db.Date, nullable=True)
    lab_name = db.Column(db.String(200), nullable=True)
    soil_health_card_no = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    farmer = db.relationship("Farmer", back_populates="soil_analyses")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "field_name": self.field_name,
            "ph": self.ph,
            "nitrogen": self.nitrogen_kg_ha,
            "phosphorus": self.phosphorus_kg_ha,
            "potassium": self.potassium_kg_ha,
            "organic_carbon": self.organic_carbon_pct,
            "ai_recommendations": self.ai_recommendations,
            "test_date": self.test_date.isoformat() if self.test_date else None,
        }


# =============================================================================
# WEATHER ALERT
# =============================================================================
class WeatherAlert(db.Model):
    """Weather alerts stored for a farmer's location."""
    __tablename__ = "weather_alerts"

    id = db.Column(db.Integer, primary_key=True)
    farmer_id = db.Column(db.Integer, db.ForeignKey("farmers.id"), nullable=False, index=True)
    alert_type = db.Column(db.String(50), nullable=False)  # rain, frost, heat, cyclone
    severity = db.Column(db.String(20), nullable=False)   # low, medium, high, critical
    message = db.Column(db.Text, nullable=False)
    farming_advisory = db.Column(db.Text, nullable=True)  # AI-generated advice
    valid_from = db.Column(db.DateTime(timezone=True), nullable=True)
    valid_until = db.Column(db.DateTime(timezone=True), nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    farmer = db.relationship("Farmer", back_populates="weather_alerts")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "message": self.message,
            "farming_advisory": self.farming_advisory,
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat(),
        }


# =============================================================================
# MANDI PRICE CACHE
# =============================================================================
class MandiPriceCache(db.Model):
    """Cached mandi prices to reduce API calls."""
    __tablename__ = "mandi_price_cache"

    id = db.Column(db.Integer, primary_key=True)
    commodity = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(60), nullable=False)
    district = db.Column(db.String(60), nullable=True)
    market = db.Column(db.String(100), nullable=True)
    variety = db.Column(db.String(100), nullable=True)
    min_price = db.Column(db.Float, nullable=True)
    max_price = db.Column(db.Float, nullable=True)
    modal_price = db.Column(db.Float, nullable=True)
    arrival_date = db.Column(db.Date, nullable=True)
    fetched_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    def to_dict(self) -> dict:
        return {
            "commodity": self.commodity,
            "state": self.state,
            "market": self.market,
            "min_price": self.min_price,
            "max_price": self.max_price,
            "modal_price": self.modal_price,
            "arrival_date": self.arrival_date.isoformat() if self.arrival_date else None,
        }


# =============================================================================
# KNOWLEDGE DOCUMENT (User-uploaded docs for RAG)
# =============================================================================
class KnowledgeDocument(db.Model):
    """Track documents uploaded to the vector store."""
    __tablename__ = "knowledge_documents"

    id = db.Column(db.Integer, primary_key=True)
    doc_id = db.Column(db.String(100), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), nullable=True)
    source = db.Column(db.String(200), nullable=True)
    chunk_count = db.Column(db.Integer, default=1)
    file_size = db.Column(db.Integer, nullable=True)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("farmers.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    is_active = db.Column(db.Boolean, default=True)
