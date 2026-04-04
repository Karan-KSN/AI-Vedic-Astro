import streamlit as st
import swisseph as swe
import datetime
import pytz
from google import genai
import json
from geopy.geocoders import Nominatim

# ==========================================
# 1. PAGE CONFIGURATION & UI SETUP
# ==========================================
st.set_page_config(page_title="The Iron Primer's AI Astrologer", page_icon="✨", layout="wide")

st.title("✨ AI Vedic Astrology Roadmap")
st.markdown("Enter your birth details to generate a mathematically precise, AI-synthesized life roadmap grounded in the wisdom of the Bhagavad Gita and Chanakya Niti.")

# Sidebar for Security
with st.sidebar:
    st.header("⚙️ Engine Configuration")
    api_key = st.text_input("Enter Google Gemini API Key:", type="password", help="Get this from Google AI Studio")
    st.markdown("---")
    st.markdown("**Note:** Your key is not saved. It is only used for the current session.")

# ==========================================
# 2. THE ASTRONOMICAL ENGINE
# ==========================================
def get_coordinates(city_name):
    """Converts a city name to Latitude and Longitude."""
    geolocator = Nominatim(user_agent="iron_primer_astrology_app")
    try:
        location = geolocator.geocode(city_name)
        if location:
            return location.latitude, location.longitude
        return None, None
    except:
        return None, None

def get_zodiac_info(longitude):
    signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", 
             "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
    sign_index = int(longitude / 30)
    degree = longitude % 30
    return signs[sign_index], round(degree, 4)

def generate_natal_matrix(year, month, day, hour, minute, lat, lon, tz_string):
    local_tz = pytz.timezone(tz_string)
    local_time = local_tz.localize(datetime.datetime(year, month, day, hour, minute))
    utc_time = local_time.astimezone(pytz.utc)

    jd = swe.julday(utc_time.year, utc_time.month, utc_time.day, 
                    utc_time.hour + utc_time.minute / 60.0)

    swe.set_sid_mode(swe.SIDM_LAHIRI)
    flags = swe.FLG_SIDEREAL | swe.FLG_SWIEPH

    planets = {
        "Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS,
        "Mercury": swe.MERCURY, "Jupiter": swe.JUPITER, 
        "Venus": swe.VENUS, "Saturn": swe.SATURN, "Rahu": swe.TRUE_NODE
    }

    chart_data = {}

    for name, planet_id in planets.items():
        pos, _ = swe.calc_ut(jd, planet_id, flags)
        lon_deg = pos[0] 
        sign, deg = get_zodiac_info(lon_deg)
        chart_data[name] = {"Sign": sign, "Degree": deg, "Total_Lon": round(lon_deg, 4)}

    ketu_lon = (chart_data["Rahu"]["Total_Lon"] + 180) % 360
    k_sign, k_deg = get_zodiac_info(ketu_lon)
    chart_data["Ketu"] = {"Sign": k_sign, "Degree": k_deg, "Total_Lon": round(ketu_lon, 4)}

    houses, ascmc = swe.houses_ex(jd, lat, lon, b'P', flags)
    asc_lon = ascmc[0]
    asc_sign, asc_deg = get_zodiac_info(asc_lon)
    chart_data["Ascendant"] = {"Sign": asc_sign, "Degree": asc_deg, "Total_Lon": round(asc_lon, 4)}

    # Map Houses and Lords directly in this step
    signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", 
             "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
             
    lords = {
        "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury", "Cancer": "Moon", 
        "Leo": "Sun", "Virgo": "Mercury", "Libra": "Venus", "Scorpio": "Mars", 
        "Sagittarius": "Jupiter", "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter"
    }
    
    asc_index = signs.index(asc_sign)

    for body, data in chart_data.items():
        if body != "Ascendant":
            planet_index = signs.index(data["Sign"])
            chart_data[body]["House"] = ((planet_index - asc_index) % 12) + 1
            chart_data[body]["Sign_Lord"] = lords[data["Sign"]]

    return chart_data

# ==========================================
# 3. THE AI SYNTHESIZER
# ==========================================
def generate_life_roadmap(matrix_data, key):
    """Feeds the calculated matrix to the AI using the new google-genai SDK."""
    print("\nInitializing AI Synthesizer...")
    
    # Using the new Google GenAI Client architecture
    client = genai.Client(api_key=key)
    
    chart_context = json.dumps(matrix_data, indent=2)

    system_prompt = f"""
    You are an elite Vedic Astrologer and strategic life guide. 
    Analyze the following mathematically exact natal chart matrix:
    
    {chart_context}
    
    Your objective is to synthesize this raw data into a highly cohesive, actionable life roadmap. 
    You must resolve any astrological contradictions seamlessly.

    Structure the output strictly as follows:
    
    ## 1. The 12-House Blueprint (Granular Matrix Analysis)
    You MUST go through every single house sequentially, starting from the 1st House (Lagna) through the 12th House. For EVERY house, explicitly state and analyze:
    * The Zodiac sign governing that house.
    * Any planets currently occupying that house.
    * The Lord of that house, and specifically which house and sign that Lord has gone to sit in.
    * The synthesized real-world effect of this specific inter-relation on the individual's life.
    (Format each house as a sub-heading: ### 1st House (Lagna), ### 2nd House (Wealth & Family), etc.)

    ## 2. Professional & Academic Roadmap
    Synthesize the overall career, wealth, and research trajectory based on the house analysis above.
    
    ## 3. Anticipated Challenges & Strategic Navigations
    Highlight key frictional points in the chart and provide strategic methods to navigate them.
    
    ## 4. Philosophical Anchor 
    Crucial Instruction: Ground your final advice in the wisdom of the Bhagavad Gita and Chanakya Niti. Use these philosophies to remind the user that while the chart shows tendencies, their Karma (action) and intellect dictate their ultimate destiny. Make them wiser and better prepared for life.
    
    Speak directly, professionally, and clearly to the individual. Use Markdown formatting.
    """

    print("Analyzing celestial data and generating granular roadmap... (This takes 5-10 seconds)\n")
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=system_prompt,
    )
    
    return response.text

# ==========================================
# 4. FRONT-END INTERFACE
# ==========================================
col1, col2 = st.columns(2)

with col1:
    dob = st.date_input("Date of Birth", min_value=datetime.date(1900, 1, 1))
    city = st.text_input("City of Birth (e.g., New Delhi, London)")

with col2:
    # Changed from a dropdown picker to a simple text input for exact minute precision
    time_str = st.text_input(
        "Time of Birth (HH:MM, 24-hour format)", 
        value="10:30", 
        help="Use 24-hour time. For example, 2:15 PM should be typed as 14:15"
    )
    
    # Safely attempt to parse the typed string into a time object
    try:
        tob = datetime.datetime.strptime(time_str, "%H:%M").time()
    except ValueError:
        st.error("⚠️ Please enter a valid time in HH:MM format (e.g., 09:05 or 14:30).")
        tob = None # This prevents the app from crashing if they type letters

    # A standard list of common timezones for the user to select
    tz_options = ["Asia/Kolkata", "America/New_York", "Europe/London", "Australia/Sydney", "UTC"]
    timezone = st.selectbox("Timezone", tz_options)

if st.button("Generate My Roadmap", type="primary"):
    # Added a check to ensure the time format is valid before running
    if not api_key:
        st.error("⚠️ Please enter your Google Gemini API Key in the sidebar first.")
    elif not city:
        st.error("⚠️ Please enter a City of Birth.")
    elif tob is None:
        st.error("⚠️ Please fix your Time of Birth format before generating.")
    else:
        with st.spinner("Calculating celestial mechanics and synthesizing roadmap..."):
            lat, lon = get_coordinates(city)
            
            if lat is None or lon is None:
                st.error("Could not find coordinates for that city. Please try a different spelling or a larger nearby city.")
            else:
                try:
                    # Run the math
                    matrix = generate_natal_matrix(
                        year=dob.year, month=dob.month, day=dob.day,
                        hour=tob.hour, minute=tob.minute,
                        lat=lat, lon=lon, tz_string=timezone
                    )
                    
                    # Run the AI
                    roadmap = generate_life_roadmap(matrix, api_key)
                    
                    # Display the results
                    st.success("Analysis Complete!")
                    st.markdown("---")
                    st.markdown(roadmap)
                    
                    with st.expander("View Raw Mathematical Matrix (For Nerds)"):
                        st.json(matrix)
                        
                except Exception as e:
                    st.error(f"An error occurred: {e}")
