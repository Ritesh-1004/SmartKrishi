"""
=============================================================================
SmartKrishi - Authentication Routes
=============================================================================
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime, timezone

from app.models.database import db, Farmer

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.home"))

    if request.method == "POST":
        data = request.form
        identifier = data.get("identifier", "").strip()
        password = data.get("password", "")

        farmer = (
            Farmer.query.filter_by(username=identifier).first()
            or Farmer.query.filter_by(email=identifier).first()
            or Farmer.query.filter_by(phone=identifier).first()
        )

        if farmer and farmer.check_password(password) and farmer.is_active:
            login_user(farmer, remember=data.get("remember") == "on")
            farmer.last_login = datetime.now(timezone.utc)
            db.session.commit()

            next_page = request.args.get("next")
            return redirect(next_page or url_for("dashboard.home"))

        flash("Invalid credentials. Please check your username and password.", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.home"))

    if request.method == "POST":
        data = request.form
        username = data.get("username", "").strip().lower()
        full_name = data.get("full_name", "").strip()
        phone = data.get("phone", "").strip()
        password = data.get("password", "")
        confirm_password = data.get("confirm_password", "")

        errors = []
        if len(username) < 3:
            errors.append("Username must be at least 3 characters.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if password != confirm_password:
            errors.append("Passwords do not match.")
        if Farmer.query.filter_by(username=username).first():
            errors.append("Username already taken.")
        if phone and Farmer.query.filter_by(phone=phone).first():
            errors.append("Phone number already registered.")

        if errors:
            for err in errors:
                flash(err, "danger")
            return render_template("auth/register.html")

        farmer = Farmer(
            username=username,
            full_name=full_name,
            phone=phone,
            email=data.get("email", "").strip() or None,
            state=data.get("state", ""),
            district=data.get("district", ""),
            preferred_language=data.get("language", "en")
        )
        farmer.set_password(password)
        db.session.add(farmer)
        db.session.commit()

        login_user(farmer)
        flash(f"Welcome to SmartKrishi, {full_name}! Your account has been created.", "success")
        return redirect(url_for("dashboard.home"))

    return render_template("auth/register.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("main.index"))


@auth_bp.route("/demo-login", methods=["POST"])
def demo_login():
    """Create/login a demo farmer account for quick testing."""
    demo_farmer = Farmer.query.filter_by(username="demo_farmer").first()

    if not demo_farmer:
        demo_farmer = Farmer(
            username="demo_farmer",
            full_name="Demo Farmer",
            phone="9999999999",
            state="Punjab",
            district="Ludhiana",
            farm_size=5.0,
            soil_type="Loamy",
            irrigation_type="Canal",
            preferred_language="en"
        )
        demo_farmer.crops = ["Wheat", "Rice", "Maize"]
        demo_farmer.set_password("demo123")
        db.session.add(demo_farmer)
        db.session.commit()

    login_user(demo_farmer)
    return redirect(url_for("dashboard.home"))
