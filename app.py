import streamlit as st
import swisseph as swe
import datetime
import pytz
from google import genai
import json
from geopy.geocoders import Nominatim
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# ==========================================
# 1. PAGE CONFIGURATION & UI SETUP
# ==========================================
st.set_page_config(page_title="Vedic AI Roadmap", page_icon="✨", layout="wide")

st.title("✨ AI Vedic Astrology Roadmap")
st.markdown("Enter birth details to generate a precise visual chart and AI-synthesized life roadmap.")

# Sidebar for Security
with st.sidebar:
    st.header("⚙️ Engine Configuration")
    api_key = st.text_input("Enter Google Gemini API Key:", type="password", help="Get this from Google AI Studio")
    st.markdown("---")
    st.markdown("**Note:** Your key is not saved. It is only used for the current session.")

# ==========================================
# 2. THE ASTRONOMICAL & DRAWING ENGINES
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

    signs_list = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", 
             "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
             
    lords = {
        "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury", "Cancer": "Moon", 
        "Leo": "Sun", "Virgo": "Mercury", "Libra": "Venus", "Scorpio": "Mars", 
        "Sagittarius": "Jupiter", "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter"
    }
    
    asc_index = signs_list.index(asc_sign)

    for body, data in chart_data.items():
        if body != "Ascendant":
            planet_index = signs_list.index(data["Sign"])
            chart_data[body]["House"] = ((planet_index - asc_index) % 12) + 1
            chart_data[body]["Sign_Lord"] = lords[data["Sign"]]

    return chart_data

def draw_north_indian_chart(chart_data):
    """Draws a North Indian style chart based on reference image geometry."""
    
    # 1. Prep Data
    rashi_names = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", 
                   "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
    
    # Organize planets by house number
    planets_by_house = {i: [] for i in range(1, 13)}
    lagna_rashi_num = 0
    
    for body, data in chart_data.items():
        if body == "Ascendant":
            lagna_rashi_num = rashi_names.index(data["Sign"]) + 1
        else:
            house_num = data["House"]
            # Shorten names for display (e.g., Jupiter -> Jup)
            short_name = body[:3] if body not in ["Rahu", "Ketu"] else body
            planets_by_house[house_num].append(short_name)

    # 2. Setup Plot
    fig, ax = plt.subplots(figsize=(8, 8), facecolor='#fdfcf5') # Light parchment background
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis('off') # Hide standard graph axes

    # 3. Draw Lines (Geometry from reference image)
    line_params = {'color': '#4a4a4a', 'linewidth': 1.5}
    
    # Outer Border
    ax.add_patch(patches.Rectangle((0, 0), 10, 10, fill=False, **line_params))
    
    # Main Diagonals
    ax.plot([0, 10], [0, 10], **line_params)
    ax.plot([0, 10], [10, 0], **line_params)
    
    # Inner Diamond
    ax.plot([5, 0], [10, 5], **line_params) # Top-mid to Left-mid
    ax.plot([0, 5], [5, 0], **line_params)  # Left-mid to Bottom-mid
    ax.plot([5, 10], [0, 5], **line_params) # Bottom-mid to Right-mid
    ax.plot([10, 5], [5, 10], **line_params)# Right-mid to Top-mid

    # 4. Define Coordinates (The visual layout maps to House Numbers)
    # North Indian layout places House 1 in the top central diamond.
    
    # Coordinates for Rashi Numbers (Corners/Points of triangles)
    rashi_coords = {
        1: (5, 5.2), 2: (0.2, 9.4), 3: (0.2, 5.2), 4: (4.8, 5.2),
        5: (0.2, 4.4), 6: (0.2, 0.2), 7: (5, 4.4), 8: (9.4, 0.2),
        9: (9.4, 4.4), 10: (5.2, 5.2), 11: (9.4, 5.2), 12: (9.4, 9.4)
    }
    
    # Coordinates for Planets (Center of triangles/diamonds)
    planet_coords = {
        1: (5, 7.5), 2: (2.5, 8.8), 3: (1.2, 7.5), 4: (2.5, 6.2),
        5: (1.2, 2.5), 6: (2.5, 1.2), 7: (5, 2.5), 8: (7.5, 1.2),
        9: (8.8, 2.5), 10: (7.5, 6.2), 11: (8.8, 7.5), 12: (7.5, 8.8)
    }

    # 5. Place Text (Rashi Numbers and Planets)
    for house_num in range(1, 13):
        # Calculate dynamic Rashi number for this house
        current_rashi_num = ((lagna_rashi_num + (house_num - 1) - 1) % 12) + 1
        
        # Draw Rashi Number (Visual structure from image)
        r_x, r_y = rashi_coords[house_num]
        
        # Special formatting for the center diamond connection points
        align = 'center'
        if house_num in [3, 5]: align = 'left'
        if house_num in [9, 11]: align = 'right'
            
        ax.text(r_x, r_y, str(current_rashi_num), fontsize=11, fontweight='bold', 
                color='#8e24aa', ha=align, va='center') # Purple for Rashi

        # Draw Planets
        planets = planets_by_house[house_num]
        if planets:
            p_x, p_y = planet_coords[house_num]
            
            # Label "Asc" for House 1
            display_text = ""
            if house_num == 1:
                display_text = "ASC\n"
            
            # Join multiple planets with newlines, limiting per line for neatness
            if len(planets) > 3:
                display_text += "\n".join(planets[:2]) + "\n" + "\n".join(planets[2:])
            else:
                display_text += "\n".join(planets)
                
            ax.text(p_x, p_y, display_text, fontsize=12, fontweight='bold',
                    color='#263238', ha='center', va='center', linespacing=1.3) # Dark Blue-Grey for planets

    st.pyplot(fig) # Render the Matplotlib chart in Streamlit

# ==========================================
# 3. THE AI SYNTHESIZER
# ==========================================
def generate_life_roadmap(matrix_data, key):
    client = genai.Client(api_key=key)
    chart_context = json.dumps(matrix_data, indent=2)

    system_prompt = f"""
    You are an elite Vedic Astrologer and strategic life guide. 
    Analyze the following mathematically exact natal chart matrix:
    
    {chart_context}
    
    Synthesize this raw data into a highly cohesive, actionable life roadmap. 
    Resolve any astrological contradictions seamlessly.
    Structure the output strictly as follows:
    
    ## 1. The 12-House Blueprint (Granular Matrix Analysis)
    You MUST go through every single house sequentially, starting from the 1st House (Lagna) through the 12th House. For EVERY house, explicitly state and analyze:
    * The Zodiac sign governing that house.
    * Any planets currently occupying that house.
    * The Lord of that house, and specifically which house and sign that Lord has gone to sit in.
    * The synthesized real-world effect of this specific inter-relation on the individual's life.
    (Format each house as a sub-heading: ### 1st House (Lagna), ### 2nd House (Wealth & Family), etc.)

    ## 2. Professional & Academic Roadmap
    ## 3. Anticipated Challenges & Strategic Navigations
    ## 4. Philosophical Anchor 
    
    Crucial Instruction for Section 4: Ground your final advice in the wisdom of the Bhagavad Gita and Chanakya Niti. 
    Speak directly, professionally, and clearly to the individual using Markdown formatting.
    """

    response = client.models.generate_content(model='gemini-2.5-flash', contents=system_prompt)
    return response.text

# ==========================================
# 4. FRONT-END INTERFACE
# ==========================================
col1, col2 = st.columns(2)

with col1:
    dob = st.date_input("Date of Birth", min_value=datetime.date(1900, 1, 1), value=datetime.date(1990, 8, 15))
    city = st.text_input("City of Birth (e.g., New Delhi, London)", value="New Delhi")

with col2:
    time_str = st.text_input("Time of Birth (HH:MM, 24-hour)", value="10:30", help="Use 24-hour format (e.g., 14:30 for 2:30 PM)")
    
    try:
        tob = datetime.datetime.strptime(time_str, "%H:%M").time()
    except ValueError:
        st.error("⚠️ Invalid time format. Use HH:MM.")
        tob = None

    tz_options = ["Asia/Kolkata", "America/New_York", "Europe/London", "Australia/Sydney", "UTC"]
    timezone = st.selectbox("Timezone", tz_options)

if st.button("Generate My Roadmap", type="primary"):
    if not api_key:
        st.error("⚠️ Please enter your Google Gemini API Key in the sidebar.")
    elif not city:
        st.error("⚠️ Please enter City.")
    elif tob is None:
        st.error("⚠️ Please fix Time format.")
    else:
        with st.spinner("Drawing chart and synthesizing roadmap..."):
            lat, lon = get_coordinates(city)
            
            if lat is None or lon is None:
                st.error("Could not find coordinates for that city.")
            else:
                try:
                    matrix = generate_natal_matrix(
                        year=dob.year, month=dob.month, day=dob.day,
                        hour=tob.hour, minute=tob.minute,
                        lat=lat, lon=lon, tz_string=timezone
                    )
                    
                    # --- NEW: Display the Chart First ---
                    st.subheader("Your Natal Chart (North Indian Style)")
                    draw_north_indian_chart(matrix)
                    st.markdown("---")
                    
                    # --- Then run and display the AI Roadmap ---
                    roadmap = generate_life_roadmap(matrix, api_key)
                    
                    st.success("Analysis Complete!")
                    st.markdown(roadmap)
                    
                except Exception as e:
                    st.error(f"An error occurred: {e}")
