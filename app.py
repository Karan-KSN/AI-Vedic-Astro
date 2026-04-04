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

# ==========================================
# 1. CORE LOGIC & DASHA CALCULATION
# ==========================================

def get_nakshatra_data(moon_lon):
    """Calculates Nakshatra, its Lord, and Dasha balance."""
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
    
    nak_index = int(moon_lon / (360/27))
    nak_name, lord, total_years = nakshatras[nak_index]
    
    # Calculate balance of current dasha at birth
    deg_in_nak = moon_lon % (360/27)
    fraction_left = ( (360/27) - deg_in_nak ) / (360/27)
    balance_years = fraction_left * total_years
    
    return nak_name, lord, balance_years

def get_current_dasha(start_lord, balance, birth_date):
    """Simple timeline to find the current Mahadasha."""
    order = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
    years = {"Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7, "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17}
    
    current_date = datetime.datetime.now()
    age_in_years = (current_date.year - birth_date.year)
    
    # Find current index in order
    idx = order.index(start_lord)
    remaining = balance
    
    while remaining < age_in_years:
        idx = (idx + 1) % 9
        remaining += years[order[idx]]
        
    return order[idx]

# [Functions for get_coordinates, generate_natal_matrix, draw_north_indian_chart remain same as previous version]
# (Ensure generate_natal_matrix is included here as per the previous working code)

# ==========================================
# 2. UPDATED AI SYNTHESIZER (PHD MODE)
# ==========================================

def generate_expert_roadmap(matrix, dasha_info, api_key):
    client = genai.Client(api_key=api_key)
    
    system_prompt = f"""
    You are an elite Vedic Astrologer and PhD Researcher in Nutrigenetics.
    User's Current Mahadasha: {dasha_info['current_lord']}
    Birth Matrix: {json.dumps(matrix)}

    Analyze this data across four specific dimensions:
    
    1. **Nutrigenetic Integration:** Correlate planetary placements with potential genetic predispositions. Specifically look for markers related to the ACE gene, hypertension, and metabolic efficiency. 
    **MANDATORY:** Back your scientific claims with relevant literature (Paper Name, Author, Year). 
    
    2. **Detailed 12-House Analysis:** Follow the dispositor chain for each house.
    
    3. **Dasha & Timing:** Explain how the current {dasha_info['current_lord']} Mahadasha will trigger specific house results.

    4. **Philosophical Anchor:** Conclude with guidance from the Bhagavad Gita and Chanakya Niti to empower the user's Karma.
    
    Speak professionally to "The Iron Primer". Use Markdown.
    """
    
    response = client.models.generate_content(model='gemini-2.5-flash', contents=system_prompt)
    return response.text

# ==========================================
# 3. UI EXECUTION
# ==========================================

# (UI code follows previous structure, but calls generate_expert_roadmap)
# ... [Include the Streamlit UI and Chart drawing functions from previous turns] ...
