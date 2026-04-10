import streamlit as st
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import swisseph as swe
import datetime
import pytz
from google import genai
import json
from geopy.geocoders import Nominatim
import io
import time

# PDF Generation
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

# ==========================================
# 1. CORE CONFIGURATION
# ==========================================

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
LORDS = {"Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury", "Cancer": "Moon", "Leo": "Sun", "Virgo": "Mercury", "Libra": "Venus", "Scorpio": "Mars", "Sagittarius": "Jupiter", "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter"}

def get_planet_dignity(planet, sign):
    dignities = {
        "Sun": {"Ex": "Aries", "Deb": "Libra"},
        "Moon": {"Ex": "Taurus", "Deb": "Scorpio"},
        "Mars": {"Ex": "Capricorn", "Deb": "Cancer"},
        "Mercury": {"Ex": "Virgo", "Deb": "Pisces"},
        "Jupiter": {"Ex": "Cancer", "Deb": "Capricorn"},
        "Venus": {"Ex": "Pisces", "Deb": "Virgo"},
        "Saturn": {"Ex": "Libra", "Deb": "Aries"}
    }
    if planet in dignities:
        if sign == dignities[planet]["Ex"]: return "Exalted"
        if sign == dignities[planet]["Deb"]: return "Debilitated"
    return "Neutral"

# ==========================================
# 2. CALCULATION ENGINE
# ==========================================

def get_coords(city):
    """Robust city lookup with increased timeout."""
    # Using a very specific user agent to avoid being blocked
    geolocator = Nominatim(user_agent="iron_primer_research_v8_final")
    try:
        location = geolocator.geocode(city, timeout=10)
        if location:
            return (location.latitude, location.longitude)
        return (None, None)
    except Exception as e:
        print(f"Geocoding error: {e}")
        return (None, None)

def get_dasha_data(moon_lon, dob):
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
    lord, yrs = nakshatras[idx][1], nakshatras[idx][2]
    bal = (( (360/27) - (moon_lon % (360/27)) ) / (360/27)) * yrs
    order = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
    d_yrs = {"Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7, "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17}
    age = (datetime.datetime.now().year - dob.year)
    d_idx = order.index(lord)
    cumul = bal
    while cumul < age:
        d_idx = (d_idx + 1) % 9
        cumul += d_yrs[order[d_idx]]
    return order[d_idx]

def calculate_chart_data(dob_str, time_str, city, tz):
    try:
        y, m, d = map(int, dob_str.split('-')[::-1])
        h, mn = map(int, time_str.split(':'))
        
        lat, lon = get_coords(city)
        if lat is None: return "CITY_NOT_FOUND"
        
        local_tz = pytz.timezone(tz)
        utc_dt = local_tz.localize(datetime.datetime(y, m, d, h, mn)).astimezone(pytz.utc)
        
        jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour + utc_dt.minute / 60.0)
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        flags = swe.FLG_SIDEREAL | swe.FLG_SWIEPH
        
        planets = {"Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS, "Mercury": swe.MERCURY, 
                   "Jupiter": swe.JUPITER, "Venus": swe.VENUS, "Saturn": swe.SATURN, "Rahu": swe.TRUE_NODE}
        
        data = {}
        for name, p_id in planets.items():
            res, _ = swe.calc_ut(jd, p_id, flags)
            lon_val = res[0]
            sign = SIGNS[int(lon_val / 30)]
            data[name] = {"Sign": sign, "Deg": round(lon_val % 30, 2), "Lon": lon_val, "Dignity": get_planet_dignity(name, sign)}
            
        data["Ketu"] = {"Sign": SIGNS[int(((data["Rahu"]["Lon"] + 180) % 360)/30)], 
                        "Deg": round((data["Rahu"]["Lon"] + 180) % 30, 2), 
                        "Lon": (data["Rahu"]["Lon"] + 180) % 360, "Dignity": "Neutral"}
        
        houses, ascmc = swe.houses_ex(jd, lat, lon, b'P', flags)
        asc_sign = SIGNS[int(ascmc[0]/30)]
        data["Ascendant"] = {"Sign": asc_sign, "Deg": round(ascmc[0]%30, 2)}
        
        a_idx = SIGNS.index(asc_sign)
        for b in data:
            if b != "Ascendant":
                p_idx = SIGNS.index(data[b]["Sign"])
                data[b]["House"] = ((p_idx - a_idx) % 12) + 1
        
        data["Dasha"] = get_dasha_data(data["Moon"]["Lon"], datetime.date(y, m, d))
        return data
    except Exception as e:
        return f"ERROR: {str(e)}"

# ==========================================
# 3. VISUALIZATION
# ==========================================

def draw_chart(data, title="Birth Chart"):
    p_by_h = {i: [] for i in range(1, 13)}
    l_idx = SIGNS.index(data["Ascendant"]["Sign"]) + 1
    for b, d in data.items():
        if b not in ["Ascendant", "Dasha"]: 
            p_by_h[d["House"]].append(b[:3] if b not in ["Rahu", "Ketu"] else b)
    
    fig, ax = plt.subplots(figsize=(5, 5), facecolor='#fdfcf5')
    ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis('off')
    lp = {'color': '#4a4a4a', 'linewidth': 1.5}
    ax.add_patch(patches.Rectangle((0, 0), 10, 10, fill=False, **lp))
    ax.plot([0, 10], [0, 10], **lp); ax.plot([0, 10], [10, 0], **lp)
    ax.plot([5, 0, 5, 10, 5], [10, 5, 0, 5, 10], **lp)
    
    rc = {1:(5,5.3), 2:(0.3,9.5), 3:(0.3,5.3), 4:(4.7,5.3), 5:(0.3,4.3), 6:(0.3,0.3), 7:(5,4.3), 8:(9.7,0.3), 9:(9.7,4.3), 10:(5.3,5.3), 11:(9.7,5.3), 12:(9.7,9.5)}
    pc = {1:(5,7.5), 2:(2.5,8.8), 3:(1.2,7.5), 4:(2.5,6.2), 5:(1.2,2.5), 6:(2.5,1.2), 7:(5,2.5), 8:(7.5,1.2), 9:(8.8,2.5), 10:(7.5,6.2), 11:(8.8,7.5), 12:(7.5,8.8)}
    
    for h in range(1, 13):
        curr_r = ((l_idx + (h - 1) - 1) % 12) + 1
        ax.text(rc[h][0], rc[h][1], str(curr_r), fontsize=8, fontweight='bold', color='#8e24aa', ha='center')
        if p_by_h[h]:
            txt = ("ASC\n" if h==1 else "") + "\n".join(p_by_h[h])
            ax.text(pc[h][0], pc[h][1], txt, fontsize=9, fontweight='bold', color='#263238', ha='center', va='center')
    plt.title(title, fontsize=12, pad=10)
    return fig

# ==========================================
# 4. STREAMLIT APP
# ==========================================

st.set_page_config(page_title="Iron Primer Research", page_icon="🧬")
st.title("🧬 Vedic Marriage & Clinical Engine")

with st.sidebar:
    st.header("🔑 Authentication")
    api_key = st.text_input("Gemini API Key", type="password")
    mode = st.radio("Analysis Mode", ["Individual Health & Life", "Marriage Longevity Analysis"])

st.subheader("👤 Individual 1 Details")
c1, c2 = st.columns(2)
with c1:
    dob1 = st.text_input("Date (DD-MM-YYYY)", value="15-08-1990", key="d1")
    city1 = st.text_input("Birth City", value="Patiala", key="c1")
with c2:
    tob1 = st.text_input("Time (HH:MM)", value="10:30", key="t1")
    tz1 = st.selectbox("Timezone", ["Asia/Kolkata", "UTC", "America/New_York"], key="z1")

if mode == "Marriage Longevity Analysis":
    st.markdown("---")
    st.subheader("👥 Individual 2 Details")
    cc1, cc2 = st.columns(2)
    with cc1:
        dob2 = st.text_input("Date (DD-MM-YYYY)", value="01-01-1992", key="d2")
        city2 = st.text_input("Birth City", value="Chandigarh", key="c2")
    with cc2:
        tob2 = st.text_input("Time (HH:MM)", value="14:15", key="t2")
        tz2 = st.selectbox("Timezone", ["Asia/Kolkata", "UTC"], key="z2")

if st.button("Generate Professional Analysis"):
    if not api_key:
        st.error("⚠️ Please enter your API Key in the sidebar.")
    else:
        # Wrap everything in a broad try-block to catch silent crashes
        try:
            with st.spinner("Processing celestial & physiological metrics..."):
                # Step 1: Calculate Chart 1
                data1 = calculate_chart_data(dob1, tob1, city1, tz1)
                
                if data1 == "CITY_NOT_FOUND":
                    st.error(f"❌ Could not find location coordinates for: {city1}")
                elif isinstance(data1, str) and "ERROR" in data1:
                    st.error(f"❌ Math Engine Error: {data1}")
                else:
                    figs = [draw_chart(data1, "Individual 1 Natal Chart")]
                    ctx = f"Person 1 Data: {json.dumps(data1)}"
                    
                    # Step 2: Handle Matchmaking if needed
                    if mode == "Marriage Longevity Analysis":
                        data2 = calculate_chart_data(dob2, tob2, city2, tz2)
                        if data2 == "CITY_NOT_FOUND":
                            st.error(f"❌ Could not find location coordinates for: {city2}")
                            st.stop()
                        figs.append(draw_chart(data2, "Individual 2 Natal Chart"))
                        ctx += f"\nPerson 2 Data: {json.dumps(data2)}"
                    
                    # Step 3: Draw the visual charts
                    for f in figs: st.pyplot(f)
                    
                    # Step 4: Call the AI interpreted Brain
                    client = genai.Client(api_key=api_key)
                    prompt = f"""
                    PhD Analysis for The Iron Primer. Context: {ctx}. Mode: {mode}.
                    1. Clinical Predispositions (Houses 6/8/12). 2. 'Sattvic' nutrition based on Agni/Water balance. 
                    3. Marriage survival prediction & Stability Index. 4. Scientific citations (Author, Year). 
                    5. Bhagavad Gita (18.14) & Chanakya Niti.
                    """
                    
                    # Resilient AI calling loop
                    report_text = ""
                    success = False
                    for model_name in ['gemini-2.0-flash', 'gemini-1.5-flash']:
                        try:
                            report = client.models.generate_content(model=model_name, contents=prompt)
                            report_text = report.text
                            success = True
                            break
                        except: continue
                    
                    if success:
                        st.markdown("---")
                        st.markdown(report_text)
                        
                        # Step 5: PDF Creation
                        buf = io.BytesIO()
                        doc = SimpleDocTemplate(buf, pagesize=A4)
                        elements = []
                        for f in figs:
                            ib = io.BytesIO(); f.savefig(ib, format='png'); ib.seek(0)
                            elements.append(Image(ib, 3*inch, 3*inch))
                        elements.append(Spacer(1, 20))
                        elements.append(Paragraph(report_text.replace('\n', '<br/>'), getSampleStyleSheet()['Normal']))
                        doc.build(elements)
                        
                        st.download_button("📥 Download PhD Report PDF", data=buf.getvalue(), file_name="Roadmap.pdf", mime="application/pdf")
                    else:
                        st.error("⚠️ AI server is busy. Please try clicking again in 30 seconds.")
                        
        except Exception as global_e:
            st.error(f"⚠️ A system error occurred: {global_e}")
