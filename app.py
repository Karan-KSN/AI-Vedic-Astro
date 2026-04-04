import streamlit as st
import swisseph as swe
import datetime
import pytz
from google import genai
import json
from geopy.geocoders import Nominatim
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import io

# PDF Generation Imports
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

# ==========================================
# 1. CORE LOGIC & DASHA CALCULATION
# ==========================================

def get_coordinates(city_name):
    """Converts a city name to Latitude and Longitude."""
    geolocator = Nominatim(user_agent="iron_primer_astrology_app")
    try:
        location = geolocator.geocode(city_name)
        return (location.latitude, location.longitude) if location else (None, None)
    except:
        return (None, None)

def get_zodiac_info(longitude):
    signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", 
             "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
    return signs[int(longitude / 30)], round(longitude % 30, 4)

def get_nakshatra_data(moon_lon):
    """Calculates Nakshatra and starting Dasha Lord."""
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
    nak_idx = int(moon_lon / (360/27))
    nak_name, lord, total_yrs = nakshatras[nak_idx]
    deg_in_nak = moon_lon % (360/27)
    balance_yrs = (( (360/27) - deg_in_nak ) / (360/27)) * total_yrs
    return {"name": nak_name, "lord": lord, "balance": balance_yrs}

def get_current_mahadasha(birth_lord, balance, birth_date):
    order = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
    years = {"Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7, "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17}
    age = (datetime.datetime.now().year - birth_date.year)
    idx = order.index(birth_lord)
    cumulative = balance
    while cumulative < age:
        idx = (idx + 1) % 9
        cumulative += years[order[idx]]
    return order[idx]

def generate_natal_matrix(year, month, day, hour, minute, lat, lon, tz_string):
    local_tz = pytz.timezone(tz_string)
    local_time = local_tz.localize(datetime.datetime(year, month, day, hour, minute))
    utc_time = local_time.astimezone(pytz.utc)
    jd = swe.julday(utc_time.year, utc_time.month, utc_time.day, utc_time.hour + utc_time.minute / 60.0)
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    flags = swe.FLG_SIDEREAL | swe.FLG_SWIEPH
    planets = {"Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS, "Mercury": swe.MERCURY, "Jupiter": swe.JUPITER, "Venus": swe.VENUS, "Saturn": swe.SATURN, "Rahu": swe.TRUE_NODE}
    chart_data = {}
    for name, p_id in planets.items():
        pos, _ = swe.calc_ut(jd, p_id, flags)
        sign, deg = get_
