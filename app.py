import streamlit as st
import matplotlib
matplotlib.use('Agg') # Essential for Streamlit Cloud stability
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import swisseph as swe
import datetime
import pytz
from google import genai
import json
from geopy.geocoders import Nominatim
import io

# PDF Generation
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

# ==========================================
# 1. GLOBAL CONSTANTS & DIGNITY LOGIC
# ==========================================

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]

LORDS = {
    "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury", "Cancer": "Moon", 
    "Leo": "Sun", "Virgo": "Mercury", "Libra": "Venus", "Scorpio": "Mars", 
    "Sagittarius": "Jupiter", "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter"
}

def get_planet_dignity(planet, sign):
    """Hardcoded lookup to ensure 100% accuracy in astrological status."""
    dignities = {
        "Sun": {"Exalted": "Aries", "Debilitated": "Libra"},
        "Moon": {"Exalted": "Taurus", "Debilitated": "Scorpio"},
        "Mars": {"Exalted": "Capricorn", "Debilitated": "Cancer"},
        "Mercury": {"Exalted": "Virgo", "Debilitated": "Pisces"},
        "Jupiter": {"Exalted": "Cancer", "Debilitated": "Capricorn"},
        "Venus": {"Exalted": "Pisces", "Debilitated": "Virgo"},
        "Saturn": {"Exalted": "Libra", "Debilitated": "Aries"}
    }
    if planet in dignities:
        if sign == dignities[planet]["Exalted"]: return "Exalted (Uchcha)"
        if sign == dignities[planet]["Debilitated"]: return "Debilitated (Neecha)"
    return "Neutral"

# ==========================================
# 2. ASTRONOMICAL & DASHA ENGINES
# ==========================================

def get_coordinates(city_name):
    geolocator = Nominatim(user_agent="iron_primer_research_app")
    try:
        location = geolocator.geocode(city_name)
        return (location.latitude, location.longitude) if location else (None, None)
    except: return (None, None)

def get_zodiac_info(longitude):
    return SIGNS[int(longitude / 30)], round(longitude % 30, 4)

def get_nakshatra_data(moon_lon):
    nakshatras = [
        ("Ashwini", "Ketu", 7), ("Bharani", "Venus", 20), ("Krittika", "Sun", 6),
        ("Rohini", "Moon", 10), ("Mrigashira", "Mars", 7), ("Ardra", "Rahu", 18),
        ("Punarvasu", "Jupiter", 16), ("Pushya", "Saturn", 19), ("Ashlesha", "Mercury", 17),
        ("Magha", "Ketu", 7), ("Purva Phalguni", "Venus", 20), ("Uttara Phalguni", "Sun", 6),
        ("Hasta", "Moon", 10), ("Chitra", "Mars", 7), ("Swati", "Rahu", 18),
        ("Vishakha", "Jupiter", 16), ("Anuradha", "Saturn", 19), ("Jyeshtha", "Mercury", 17),
        ("Mula", "Ketu", 7), ("Purva Ashadha", "Venus", 20), ("Uttara Ashadha", "Sun", 6),
        ("Shravana", "Moon", 10), ("Dhanishta", "Mars", 7), ("Shatabhisha", "Rahu", 18),
        ("Purva Bhadrapada", "Jupiter", 16), ("Uttara Bhadrapada", "Saturn", 19), ("Revati", "Mercury", 17)
    ]
    idx = int(moon_lon / (360/27))
    name, lord, yrs = nakshatras[idx]
    bal = (( (360/27) - (moon_lon % (360/27)) ) / (360/27)) * yrs
