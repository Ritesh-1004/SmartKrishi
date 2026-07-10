"""
=============================================================================
SmartKrishi - Dashboard Routes
=============================================================================
"""

from flask import Blueprint, render_template
from flask_login import login_required, current_user

from app.models.database import ChatSession, SoilAnalysis, WeatherAlert

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def home():
    recent_sessions = ChatSession.query.filter_by(
        farmer_id=current_user.id
    ).order_by(ChatSession.updated_at.desc()).limit(5).all()

    recent_analyses = SoilAnalysis.query.filter_by(
        farmer_id=current_user.id
    ).order_by(SoilAnalysis.created_at.desc()).limit(3).all()

    unread_alerts = WeatherAlert.query.filter_by(
        farmer_id=current_user.id, is_read=False
    ).count()

    return render_template("dashboard/home.html",
                           recent_sessions=recent_sessions,
                           recent_analyses=recent_analyses,
                           unread_alerts=unread_alerts)


@dashboard_bp.route("/chat")
@login_required
def chat():
    sessions = ChatSession.query.filter_by(
        farmer_id=current_user.id, is_archived=False
    ).order_by(ChatSession.updated_at.desc()).limit(20).all()
    return render_template("dashboard/chat.html", sessions=sessions)


@dashboard_bp.route("/soil")
@login_required
def soil():
    analyses = SoilAnalysis.query.filter_by(
        farmer_id=current_user.id
    ).order_by(SoilAnalysis.created_at.desc()).all()
    return render_template("dashboard/soil.html", analyses=analyses)


@dashboard_bp.route("/weather")
@login_required
def weather():
    return render_template("dashboard/weather.html")


@dashboard_bp.route("/mandi")
@login_required
def mandi():
    return render_template("dashboard/mandi.html")


@dashboard_bp.route("/schemes")
@login_required
def schemes():
    return render_template("dashboard/schemes.html")


@dashboard_bp.route("/profile")
@login_required
def profile():
    return render_template("dashboard/profile.html")
