"""
=============================================================================
SmartKrishi - Tests
Basic smoke tests for routes, models, and services
=============================================================================
"""

import pytest
import os
os.environ["FLASK_ENV"] = "testing"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["TESTING"] = "true"


@pytest.fixture
def app():
    from app import create_app
    application = create_app("testing")
    application.config["TESTING"] = True
    application.config["WTF_CSRF_ENABLED"] = False
    application.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    return application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    from app.models.database import db as database
    with app.app_context():
        database.create_all()
        yield database
        database.drop_all()


class TestHealthCheck:
    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "healthy"
        assert "version" in data


class TestAuthRoutes:
    def test_login_page_loads(self, client):
        response = client.get("/auth/login")
        assert response.status_code == 200

    def test_register_page_loads(self, client):
        response = client.get("/auth/register")
        assert response.status_code == 200

    def test_register_creates_user(self, client, db):
        response = client.post("/auth/register", data={
            "username": "test_farmer",
            "full_name": "Test Farmer",
            "phone": "9876543210",
            "password": "testpass123",
            "confirm_password": "testpass123",
            "state": "Punjab",
            "language": "en"
        }, follow_redirects=True)
        assert response.status_code == 200


class TestAPIEndpoints:
    def test_chat_requires_message(self, client):
        response = client.post("/api/chat",
            json={},
            content_type="application/json")
        assert response.status_code == 400

    def test_chat_demo_response(self, client):
        response = client.post("/api/chat",
            json={"message": "What crops should I grow?"},
            content_type="application/json")
        assert response.status_code == 200
        data = response.get_json()
        assert "response" in data

    def test_weather_api(self, client):
        response = client.get("/api/weather?city=Delhi")
        assert response.status_code in [200, 503]

    def test_mandi_prices(self, client):
        response = client.get("/api/mandi-prices?commodity=Wheat")
        assert response.status_code == 200
        data = response.get_json()
        assert "prices" in data

    def test_soil_analysis(self, client):
        response = client.post("/api/soil-analysis",
            json={"ph": 6.5, "nitrogen": 220, "crop": "Rice"},
            content_type="application/json")
        assert response.status_code == 200
        data = response.get_json()
        assert "recommendations" in data


class TestModels:
    def test_farmer_model(self, db, app):
        from app.models.database import Farmer
        with app.app_context():
            farmer = Farmer(
                username="test_user",
                full_name="Test User",
                phone="9876543210"
            )
            farmer.set_password("password123")
            db.session.add(farmer)
            db.session.commit()

            retrieved = Farmer.query.filter_by(username="test_user").first()
            assert retrieved is not None
            assert retrieved.check_password("password123")
            assert not retrieved.check_password("wrongpass")

    def test_farmer_crops_json(self, db, app):
        from app.models.database import Farmer
        with app.app_context():
            farmer = Farmer(username="crop_test", full_name="Crop Test", phone="9000000001")
            farmer.set_password("pass")
            farmer.crops = ["Wheat", "Rice", "Maize"]
            db.session.add(farmer)
            db.session.commit()

            retrieved = Farmer.query.filter_by(username="crop_test").first()
            assert retrieved.crops == ["Wheat", "Rice", "Maize"]


class TestAgentInstructions:
    def test_system_prompt_builds(self):
        from app.agent_instructions import build_system_prompt
        prompt = build_system_prompt(language="en")
        assert len(prompt) > 100
        assert "KrishiMitra" in prompt

    def test_system_prompt_with_profile(self):
        from app.agent_instructions import build_system_prompt
        profile = {"name": "Ravi", "state": "Punjab", "crops": ["Wheat"]}
        prompt = build_system_prompt(language="hi", farmer_profile=profile)
        assert "Ravi" in prompt
        assert "Punjab" in prompt


class TestRAGPipeline:
    def test_context_builder(self):
        from app.rag.pipeline import ContextBuilder
        docs = [
            {"content": "Rice blast is a fungal disease.", "metadata": {"category": "disease"}, "relevance_score": 0.9}
        ]
        context = ContextBuilder.build_context(docs)
        assert "Rice blast" in context
        assert "DISEASE" in context

    def test_document_processor_chunking(self):
        from app.rag.pipeline import DocumentProcessor
        processor = DocumentProcessor(chunk_size=100, chunk_overlap=10)
        text = "A" * 250
        chunks = processor.chunk_text(text)
        assert len(chunks) > 1
        assert all(len(c) <= 110 for c in chunks)  # slight tolerance for boundary
