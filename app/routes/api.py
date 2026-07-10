"""
=============================================================================
SmartKrishi - Main API Routes
Core chat, RAG, weather, mandi prices, and soil analysis endpoints
=============================================================================
"""

import time
import logging
import os
from datetime import datetime, date

from flask import Blueprint, request, jsonify, session
from flask_login import login_required, current_user

from app.models.database import db, ChatSession, ChatMessage, SoilAnalysis, MandiPriceCache, WeatherAlert
from app.services.watsonx_service import watsonx_service, translation_service
from app.rag.pipeline import vector_store, context_builder
from app.agent_instructions import build_system_prompt, PROMPT_TEMPLATES

logger = logging.getLogger(__name__)
api_bp = Blueprint("api", __name__)


# =============================================================================
# CHAT / AI ENDPOINTS
# =============================================================================
@api_bp.route("/chat", methods=["POST"])
def chat():
    """
    Main AI chat endpoint.
    Supports both authenticated (personalized) and anonymous usage.
    """
    start_time = time.time()
    data = request.get_json(silent=True) or {}

    user_message = (data.get("message") or "").strip()
    if not user_message:
        return jsonify({"error": "Message is required"}), 400

    if len(user_message) > 2000:
        return jsonify({"error": "Message too long (max 2000 characters)"}), 400

    session_id = data.get("session_id")
    language = data.get("language", "en")
    is_voice = data.get("is_voice", False)
    context_type = data.get("context_type", "general")

    # Detect language if not specified
    if language == "auto":
        language = translation_service.detect_language(user_message)

    # Get farmer profile for personalization
    farmer_profile = None
    if current_user.is_authenticated:
        farmer_profile = current_user.to_profile_dict()
        language = farmer_profile.get("language", language)

    # ── Get or create chat session ──────────────────────────────────────────
    chat_session = None
    conversation_history = []

    if session_id and current_user.is_authenticated:
        chat_session = ChatSession.query.filter_by(
            id=session_id, farmer_id=current_user.id
        ).first()

        if chat_session:
            # Get last 6 messages for context
            recent_msgs = ChatMessage.query.filter_by(
                session_id=chat_session.id
            ).order_by(ChatMessage.timestamp.desc()).limit(6).all()
            conversation_history = [m.to_dict() for m in reversed(recent_msgs)]

    if not chat_session and current_user.is_authenticated:
        chat_session = ChatSession(
            farmer_id=current_user.id,
            title=user_message[:50] + ("..." if len(user_message) > 50 else ""),
            language=language,
            context_type=context_type
        )
        db.session.add(chat_session)
        db.session.flush()

    # ── RAG: Retrieve relevant context ─────────────────────────────────────
    rag_docs = vector_store.query(user_message, n_results=5)
    rag_context = context_builder.build_context(rag_docs)
    augmented_prompt = context_builder.build_augmented_prompt(
        user_message, rag_context, conversation_history
    )

    # ── Build system prompt ─────────────────────────────────────────────────
    system_prompt = build_system_prompt(language=language, farmer_profile=farmer_profile)

    # ── Generate AI response ────────────────────────────────────────────────
    result = watsonx_service.generate(
        system_prompt=system_prompt,
        user_message=augmented_prompt,
        max_tokens=1024,
        temperature=0.7
    )

    response_text = result["text"]
    elapsed_ms = int((time.time() - start_time) * 1000)

    # ── Save messages to DB ─────────────────────────────────────────────────
    if chat_session:
        user_msg = ChatMessage(
            session_id=chat_session.id,
            role="user",
            content=user_message,
            language=language,
            is_voice_input=is_voice,
            timestamp=datetime.utcnow()
        )
        ai_msg = ChatMessage(
            session_id=chat_session.id,
            role="assistant",
            content=response_text,
            language=language,
            rag_context_used=bool(rag_docs),
            rag_docs_retrieved=len(rag_docs),
            model_used=result.get("model"),
            tokens_used=result.get("tokens_used", 0),
            response_time_ms=elapsed_ms,
            timestamp=datetime.utcnow()
        )
        db.session.add_all([user_msg, ai_msg])
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"DB commit error: {e}")

    return jsonify({
        "response": response_text,
        "session_id": chat_session.id if chat_session else None,
        "language": language,
        "rag_used": bool(rag_docs),
        "rag_docs_count": len(rag_docs),
        "response_time_ms": elapsed_ms,
        "model": result.get("model"),
        "is_demo": result.get("is_demo", False),
        "success": result.get("success", True)
    })


@api_bp.route("/chat/sessions", methods=["GET"])
@login_required
def get_chat_sessions():
    """Get all chat sessions for the current farmer."""
    sessions = ChatSession.query.filter_by(
        farmer_id=current_user.id, is_archived=False
    ).order_by(ChatSession.updated_at.desc()).limit(20).all()

    return jsonify({
        "sessions": [s.to_dict() for s in sessions]
    })


@api_bp.route("/chat/sessions/<int:session_id>/messages", methods=["GET"])
@login_required
def get_session_messages(session_id):
    """Get all messages in a chat session."""
    chat_session = ChatSession.query.filter_by(
        id=session_id, farmer_id=current_user.id
    ).first_or_404()

    messages = ChatMessage.query.filter_by(
        session_id=session_id
    ).order_by(ChatMessage.timestamp).all()

    return jsonify({
        "session": chat_session.to_dict(),
        "messages": [m.to_dict() for m in messages]
    })


# =============================================================================
# WEATHER ENDPOINTS
# =============================================================================
@api_bp.route("/weather", methods=["GET"])
def get_weather():
    """Get weather data and farming advisory for a location."""
    lat = request.args.get("lat")
    lon = request.args.get("lon")
    city = request.args.get("city", "Delhi")

    weather_data = _fetch_weather(lat, lon, city)
    if not weather_data:
        return jsonify({"error": "Weather data unavailable"}), 503

    # Generate AI farming advisory for weather
    advisory = _generate_weather_advisory(weather_data)
    weather_data["farming_advisory"] = advisory

    return jsonify(weather_data)


def _fetch_weather(lat=None, lon=None, city="Delhi") -> dict:
    """Fetch weather from OpenWeatherMap API."""
    api_key = os.getenv("WEATHER_API_KEY")

    # Return demo data if no API key
    if not api_key:
        return _demo_weather_data(city)

    try:
        import requests

        base_url = os.getenv("WEATHER_BASE_URL", "https://api.openweathermap.org/data/2.5")

        if lat and lon:
            url = f"{base_url}/forecast?lat={lat}&lon={lon}&appid={api_key}&units=metric&cnt=40"
        else:
            url = f"{base_url}/forecast?q={city},IN&appid={api_key}&units=metric&cnt=40"

        response = requests.get(url, timeout=10)
        if response.ok:
            raw = response.json()
            return _parse_weather_data(raw)

    except Exception as e:
        logger.error(f"Weather API error: {e}")

    return _demo_weather_data(city)


def _parse_weather_data(raw: dict) -> dict:
    """Parse OpenWeatherMap forecast response."""
    city_info = raw.get("city", {})
    items = raw.get("list", [])

    today = {}
    forecast = []
    seen_dates = set()

    for item in items:
        dt_txt = item.get("dt_txt", "")
        date_str = dt_txt[:10]
        hour = int(dt_txt[11:13]) if len(dt_txt) > 11 else 0

        if not today and hour in [12, 13, 14]:
            today = {
                "temp": round(item["main"]["temp"]),
                "feels_like": round(item["main"]["feels_like"]),
                "humidity": item["main"]["humidity"],
                "description": item["weather"][0]["description"].title(),
                "icon": item["weather"][0]["icon"],
                "wind_speed": round(item["wind"]["speed"] * 3.6, 1),
                "rain": item.get("rain", {}).get("3h", 0),
            }

        if date_str not in seen_dates and hour == 12:
            seen_dates.add(date_str)
            forecast.append({
                "date": date_str,
                "temp_max": round(item["main"]["temp_max"]),
                "temp_min": round(item["main"]["temp_min"]),
                "description": item["weather"][0]["description"].title(),
                "icon": item["weather"][0]["icon"],
                "humidity": item["main"]["humidity"],
                "rain": item.get("rain", {}).get("3h", 0),
            })

    return {
        "city": city_info.get("name", "Unknown"),
        "country": city_info.get("country", "IN"),
        "current": today or {
            "temp": 28, "humidity": 65, "description": "Partly Cloudy",
            "icon": "04d", "wind_speed": 12, "rain": 0
        },
        "forecast": forecast[:7]
    }


def _generate_weather_advisory(weather_data: dict) -> str:
    """Generate AI-powered farming advisory based on weather."""
    current = weather_data.get("current", {})
    temp = current.get("temp", 28)
    humidity = current.get("humidity", 60)
    rain = current.get("rain", 0)

    advisories = []

    if rain > 10:
        advisories.append("Heavy rainfall expected — delay spraying operations. Ensure proper field drainage to prevent waterlogging.")
    elif rain > 2:
        advisories.append("Light to moderate rain expected — good for crop growth. Monitor for fungal diseases in humid conditions.")

    if humidity > 85:
        advisories.append("High humidity alert — risk of fungal diseases (blight, rust, mildew). Apply preventive fungicide spray.")

    if temp > 40:
        advisories.append("Heat stress warning — irrigate crops in early morning or evening. Mulching can help retain soil moisture.")
    elif temp < 10:
        advisories.append("Cold wave alert — protect crops from frost. Cover young seedlings and avoid night irrigation.")

    if not advisories:
        advisories.append("Favorable weather conditions for most farming operations. Good time for field preparations and crop care activities.")

    return " ".join(advisories)


def _demo_weather_data(city: str) -> dict:
    """Demo weather data when API key not configured."""
    return {
        "city": city,
        "country": "IN",
        "current": {
            "temp": 30,
            "feels_like": 34,
            "humidity": 68,
            "description": "Partly Cloudy",
            "icon": "04d",
            "wind_speed": 14.4,
            "rain": 0
        },
        "forecast": [
            {"date": "2024-11-20", "temp_max": 32, "temp_min": 22, "description": "Sunny", "icon": "01d", "humidity": 55, "rain": 0},
            {"date": "2024-11-21", "temp_max": 29, "temp_min": 21, "description": "Light Rain", "icon": "10d", "humidity": 75, "rain": 5.2},
            {"date": "2024-11-22", "temp_max": 27, "temp_min": 20, "description": "Cloudy", "icon": "04d", "humidity": 80, "rain": 2.1},
            {"date": "2024-11-23", "temp_max": 31, "temp_min": 22, "description": "Sunny", "icon": "01d", "humidity": 60, "rain": 0},
            {"date": "2024-11-24", "temp_max": 33, "temp_min": 23, "description": "Partly Cloudy", "icon": "02d", "humidity": 58, "rain": 0},
            {"date": "2024-11-25", "temp_max": 30, "temp_min": 21, "description": "Thunderstorm", "icon": "11d", "humidity": 85, "rain": 18.5},
            {"date": "2024-11-26", "temp_max": 28, "temp_min": 20, "description": "Light Rain", "icon": "10d", "humidity": 78, "rain": 4.0},
        ],
        "farming_advisory": "Weather conditions are generally favorable. Monitor humidity levels and watch for potential fungal disease outbreaks.",
        "is_demo": True
    }


# =============================================================================
# MANDI PRICES ENDPOINT
# =============================================================================
@api_bp.route("/mandi-prices", methods=["GET"])
def get_mandi_prices():
    """Get live mandi prices for commodities."""
    commodity = request.args.get("commodity", "Wheat")
    state = request.args.get("state", "")

    # Check cache (data less than 6 hours old)
    from sqlalchemy import and_, func
    from datetime import timedelta
    cache_cutoff = datetime.utcnow() - timedelta(hours=6)

    query = MandiPriceCache.query.filter(
        MandiPriceCache.commodity.ilike(f"%{commodity}%"),
        MandiPriceCache.fetched_at >= cache_cutoff
    )
    if state:
        query = query.filter(MandiPriceCache.state.ilike(f"%{state}%"))

    cached = query.order_by(MandiPriceCache.modal_price.desc()).limit(20).all()

    if cached:
        return jsonify({
            "commodity": commodity,
            "prices": [p.to_dict() for p in cached],
            "source": "cache",
            "last_updated": cached[0].fetched_at.isoformat()
        })

    # Fetch fresh data
    prices = _fetch_mandi_prices(commodity, state)
    return jsonify({"commodity": commodity, "prices": prices, "source": "api"})


def _fetch_mandi_prices(commodity: str, state: str = "") -> list:
    """Fetch from data.gov.in Agmarknet API."""
    api_key = os.getenv("MANDI_API_KEY")

    if not api_key:
        return _demo_mandi_prices(commodity)

    try:
        import requests
        params = {
            "api-key": api_key,
            "format": "json",
            "filters[commodity]": commodity,
            "limit": 50
        }
        if state:
            params["filters[state]"] = state

        response = requests.get(os.getenv("MANDI_API_URL"), params=params, timeout=15)
        if response.ok:
            data = response.json()
            records = data.get("records", [])

            # Cache results
            for rec in records:
                price_rec = MandiPriceCache(
                    commodity=rec.get("commodity", commodity),
                    state=rec.get("state", ""),
                    district=rec.get("district", ""),
                    market=rec.get("market", ""),
                    variety=rec.get("variety", ""),
                    min_price=_safe_float(rec.get("min_price")),
                    max_price=_safe_float(rec.get("max_price")),
                    modal_price=_safe_float(rec.get("modal_price")),
                    arrival_date=_safe_date(rec.get("arrival_date"))
                )
                db.session.add(price_rec)
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()

            return [MandiPriceCache(**{
                "commodity": r.get("commodity"),
                "state": r.get("state"),
                "market": r.get("market"),
                "min_price": _safe_float(r.get("min_price")),
                "max_price": _safe_float(r.get("max_price")),
                "modal_price": _safe_float(r.get("modal_price")),
                "arrival_date": _safe_date(r.get("arrival_date"))
            }).to_dict() for r in records[:20]]

    except Exception as e:
        logger.error(f"Mandi API error: {e}")

    return _demo_mandi_prices(commodity)


def _demo_mandi_prices(commodity: str) -> list:
    """Demo mandi prices data."""
    return [
        {"commodity": commodity, "state": "Punjab", "market": "Ludhiana", "min_price": 2050, "max_price": 2200, "modal_price": 2100, "arrival_date": "2024-11-19"},
        {"commodity": commodity, "state": "Haryana", "market": "Ambala", "min_price": 2000, "max_price": 2180, "modal_price": 2080, "arrival_date": "2024-11-19"},
        {"commodity": commodity, "state": "Uttar Pradesh", "market": "Agra", "min_price": 1980, "max_price": 2150, "modal_price": 2060, "arrival_date": "2024-11-19"},
        {"commodity": commodity, "state": "Madhya Pradesh", "market": "Bhopal", "min_price": 1950, "max_price": 2120, "modal_price": 2020, "arrival_date": "2024-11-19"},
        {"commodity": commodity, "state": "Rajasthan", "market": "Jaipur", "min_price": 1990, "max_price": 2160, "modal_price": 2050, "arrival_date": "2024-11-19"},
    ]


# =============================================================================
# SOIL ANALYSIS ENDPOINT
# =============================================================================
@api_bp.route("/soil-analysis", methods=["POST"])
def analyze_soil():
    """Analyze soil parameters and return AI recommendations."""
    data = request.get_json(silent=True) or {}

    soil_params = {
        "ph": data.get("ph"),
        "nitrogen": data.get("nitrogen"),
        "phosphorus": data.get("phosphorus"),
        "potassium": data.get("potassium"),
        "organic_carbon": data.get("organic_carbon"),
        "sulphur": data.get("sulphur"),
        "zinc": data.get("zinc"),
        "intended_crop": data.get("crop", "General")
    }

    # Build soil analysis prompt
    template = PROMPT_TEMPLATES["soil_analysis"]
    prompt = template.format(
        ph=soil_params["ph"] or "Not provided",
        nitrogen=soil_params["nitrogen"] or "Not provided",
        phosphorus=soil_params["phosphorus"] or "Not provided",
        potassium=soil_params["potassium"] or "Not provided",
        organic_carbon=soil_params["organic_carbon"] or "Not provided",
        other=f"Sulphur: {soil_params['sulphur'] or 'N/A'}, Zinc: {soil_params['zinc'] or 'N/A'}",
        crop=soil_params["intended_crop"]
    )

    farmer_profile = current_user.to_profile_dict() if current_user.is_authenticated else None
    system_prompt = build_system_prompt(farmer_profile=farmer_profile)
    rag_docs = vector_store.query(f"soil analysis {soil_params['intended_crop']} fertilizer recommendation")
    rag_context = context_builder.build_context(rag_docs)

    result = watsonx_service.generate(
        system_prompt=system_prompt,
        user_message=rag_context + "\n" + prompt,
        max_tokens=1200
    )

    # Save to DB if authenticated
    if current_user.is_authenticated:
        analysis = SoilAnalysis(
            farmer_id=current_user.id,
            ph=_safe_float(soil_params["ph"]),
            nitrogen_kg_ha=_safe_float(soil_params["nitrogen"]),
            phosphorus_kg_ha=_safe_float(soil_params["phosphorus"]),
            potassium_kg_ha=_safe_float(soil_params["potassium"]),
            organic_carbon_pct=_safe_float(soil_params["organic_carbon"]),
            sulphur_ppm=_safe_float(soil_params["sulphur"]),
            zinc_ppm=_safe_float(soil_params["zinc"]),
            ai_recommendations=result["text"],
            test_date=date.today()
        )
        db.session.add(analysis)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    return jsonify({
        "recommendations": result["text"],
        "soil_health_score": _calculate_soil_score(soil_params),
        "deficiencies": _identify_deficiencies(soil_params),
        "success": result["success"]
    })


# =============================================================================
# CROP RECOMMENDATION ENDPOINT
# =============================================================================
@api_bp.route("/crop-recommendation", methods=["POST"])
def get_crop_recommendation():
    """Get AI crop recommendations based on soil and conditions."""
    data = request.get_json(silent=True) or {}

    template = PROMPT_TEMPLATES["crop_recommendation"]
    prompt = template.format(
        region=data.get("region", "India"),
        season=data.get("season", "Kharif"),
        soil_type=data.get("soil_type", "Loamy"),
        water=data.get("water", "Canal irrigation"),
        farm_size=data.get("farm_size", 2),
        previous_crop=data.get("previous_crop", "None"),
        budget=data.get("budget", "Medium")
    )

    rag_docs = vector_store.query(
        f"crop recommendation {data.get('season', 'kharif')} {data.get('soil_type', 'loam')} {data.get('region', '')}"
    )
    rag_context = context_builder.build_context(rag_docs)

    farmer_profile = current_user.to_profile_dict() if current_user.is_authenticated else None
    system_prompt = build_system_prompt(farmer_profile=farmer_profile)

    result = watsonx_service.generate(
        system_prompt=system_prompt,
        user_message=rag_context + "\n" + prompt
    )

    return jsonify({"recommendations": result["text"], "success": result["success"]})


# =============================================================================
# TRANSLATE ENDPOINT
# =============================================================================
@api_bp.route("/translate", methods=["POST"])
def translate_text():
    """Translate text to specified language."""
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    target_lang = data.get("target", "en")
    source_lang = data.get("source", "auto")

    if not text:
        return jsonify({"error": "Text is required"}), 400

    translated = translation_service.translate(text, target_lang, source_lang)
    detected = translation_service.detect_language(text)

    return jsonify({
        "translated": translated,
        "detected_language": detected,
        "target_language": target_lang
    })


# =============================================================================
# FARMER PROFILE ENDPOINTS
# =============================================================================
@api_bp.route("/profile", methods=["GET"])
@login_required
def get_profile():
    return jsonify(current_user.to_public_dict())


@api_bp.route("/profile", methods=["PUT"])
@login_required
def update_profile():
    data = request.get_json(silent=True) or {}
    allowed = ["full_name", "state", "district", "village", "pincode",
               "farm_size", "soil_type", "irrigation_type", "preferred_language",
               "dark_mode", "voice_enabled", "latitude", "longitude"]

    for field in allowed:
        if field in data:
            setattr(current_user, field, data[field])

    if "crops" in data and isinstance(data["crops"], list):
        current_user.crops = data["crops"]

    try:
        db.session.commit()
        return jsonify({"success": True, "profile": current_user.to_public_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# =============================================================================
# GOVERNMENT SCHEMES ENDPOINT
# =============================================================================
@api_bp.route("/schemes", methods=["GET"])
def get_schemes():
    """Get AI-curated information about government agricultural schemes."""
    category = request.args.get("category", "")
    state = request.args.get("state", "")
    need = request.args.get("need", "")

    query_text = f"government agricultural scheme {category} {state} {need}".strip()
    rag_docs = vector_store.query(query_text, n_results=5)
    rag_context = context_builder.build_context(rag_docs)

    template = PROMPT_TEMPLATES["government_scheme"]
    prompt = template.format(
        category=category or "small farmer",
        state=state or "India",
        need=need or "general support",
        crop=request.args.get("crop", "all crops")
    )

    system_prompt = build_system_prompt()
    result = watsonx_service.generate(
        system_prompt=system_prompt,
        user_message=rag_context + "\n" + prompt,
        max_tokens=1200
    )

    return jsonify({"information": result["text"], "success": result["success"]})


# =============================================================================
# UTILITIES
# =============================================================================
def _safe_float(val) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _safe_date(val) -> date:
    if not val:
        return None
    try:
        return datetime.strptime(val, "%d/%m/%Y").date()
    except Exception:
        try:
            return datetime.fromisoformat(val).date()
        except Exception:
            return None


def _calculate_soil_score(params: dict) -> int:
    """Calculate a simple soil health score 0-100."""
    score = 50  # Base score
    ph = _safe_float(params.get("ph"))
    oc = _safe_float(params.get("organic_carbon"))
    n = _safe_float(params.get("nitrogen"))

    if ph:
        if 6.0 <= ph <= 7.5:
            score += 20
        elif 5.5 <= ph <= 8.0:
            score += 10
    if oc:
        if oc >= 0.75:
            score += 15
        elif oc >= 0.5:
            score += 8
    if n:
        if n >= 280:
            score += 15
        elif n >= 140:
            score += 8

    return min(100, max(0, score))


def _identify_deficiencies(params: dict) -> list:
    """Identify nutrient deficiencies from soil parameters."""
    deficiencies = []
    ph = _safe_float(params.get("ph"))
    n = _safe_float(params.get("nitrogen"))
    p = _safe_float(params.get("phosphorus"))
    k = _safe_float(params.get("potassium"))
    oc = _safe_float(params.get("organic_carbon"))

    if ph and ph < 6.0:
        deficiencies.append({"nutrient": "pH", "status": "Acidic", "severity": "high"})
    if ph and ph > 8.5:
        deficiencies.append({"nutrient": "pH", "status": "Alkaline", "severity": "high"})
    if n and n < 140:
        deficiencies.append({"nutrient": "Nitrogen (N)", "status": "Low", "severity": "high" if n < 100 else "medium"})
    if p and p < 11:
        deficiencies.append({"nutrient": "Phosphorus (P)", "status": "Low", "severity": "high" if p < 7 else "medium"})
    if k and k < 108:
        deficiencies.append({"nutrient": "Potassium (K)", "status": "Low", "severity": "high" if k < 75 else "medium"})
    if oc and oc < 0.5:
        deficiencies.append({"nutrient": "Organic Carbon", "status": "Very Low", "severity": "high"})

    return deficiencies
