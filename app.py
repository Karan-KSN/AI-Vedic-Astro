import streamlit as st
import matplotlib
matplotlib.use('Agg') # CRITICAL: Prevents "Black Screen" on cloud servers
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
# 1. CORE MATH & DASHA LOGIC
# ==========================================

def get_coordinates(city_name):
    geolocator = Nominatim(user_agent="iron_primer_research_app")
    try:
        location = geolocator.geocode(city_name)
        return (location.latitude, location.longitude) if location else (None, None)
    except: return (None, None)

def get_zodiac_info(longitude):
    signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
    return signs[int(longitude / 30)], round(longitude % 30, 4)

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
    deg_in = moon_lon % (360/27)
    bal = (( (360/27) - deg_in ) / (360/27)) * yrs
    return {"name": name, "lord": lord, "balance": bal}

def get_current_mahadasha(birth_lord, balance, birth_date):
    order = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
    years = {"Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7, "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17}
    age = (datetime.datetime.now().year - birth_date.year)
    idx = order.index(birth_lord)
    cumul = balance
    while cumul < age:
        idx = (idx + 1) % 9
        cumul += years[order[idx]]
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
        sign, deg = get_zodiac_info(pos[0])
        chart_data[name] = {"Sign": sign, "Degree": deg, "Total_Lon": round(pos[0], 4)}
    k_lon = (chart_data["Rahu"]["Total_Lon"] + 180) % 360
    ksign, kdeg = get_zodiac_info(k_lon)
    chart_data["Ketu"] = {"Sign": ksign, "Degree": kdeg, "Total_Lon": round(k_lon, 4)}
    houses, ascmc = swe.houses_ex(jd, lat, lon, b'P', flags)
    asc_sign, asc_deg = get_zodiac_info(ascmc[0])
    chart_data["Ascendant"] = {"Sign": asc_sign, "Degree": asc_deg, "Total_Lon": round(ascmc[0], 4)}
    
    s_list = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
    lords = {"Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury", "Cancer": "Moon", "Leo": "Sun", "Virgo": "Mercury", "Libra": "Venus", "Scorpio": "Mars", "Sagittarius": "Jupiter", "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter"}
    a_idx = s_list.index(asc_sign)
    for b, d in chart_data.items():
        if b != "Ascendant":
            p_idx = s_list.index(d["Sign"])
            chart_data[b]["House"] = ((p_idx - a_idx) % 12) + 1
            chart_data[b]["Sign_Lord"] = lords[d["Sign"]]
    return chart_data

# ==========================================
# 2. DRAWING & PDF ENGINE
# ==========================================

def draw_north_indian_chart(chart_data):
    r_names = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
    p_by_h = {i: [] for i in range(1, 13)}
    l_idx = r_names.index(chart_data["Ascendant"]["Sign"]) + 1
    for body, data in chart_data.items():
        if body != "Ascendant":
            s_name = body[:3] if body not in ["Rahu", "Ketu"] else body
            p_by_h[data["House"]].append(s_name)
    
    fig, ax = plt.subplots(figsize=(6, 6), facecolor='#fdfcf5')
    ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis('off')
    l_p = {'color': '#4a4a4a', 'linewidth': 1.5}
    ax.add_patch(patches.Rectangle((0, 0), 10, 10, fill=False, **l_p))
    ax.plot([0, 10], [0, 10], **l_p); ax.plot([0, 10], [10, 0], **l_p)
    ax.plot([5, 0, 5, 10, 5], [10, 5, 0, 5, 10], **l_p)
    
    r_c = {1:(5,5.2), 2:(0.2,9.4), 3:(0.2,5.2), 4:(4.8,5.2), 5:(0.2,4.4), 6:(0.2,0.2), 7:(5,4.4), 8:(9.4,0.2), 9:(9.4,4.4), 10:(5.2,5.2), 11:(9.4,5.2), 12:(9.4,9.4)}
    p_c = {1:(5,7.5), 2:(2.5,8.8), 3:(1.2,7.5), 4:(2.5,6.2), 5:(1.2,2.5), 6:(2.5,1.2), 7:(5,2.5), 8:(7.5,1.2), 9:(8.8,2.5), 10:(7.5,6.2), 11:(8.8,7.5), 12:(7.5,8.8)}
    
    for h in range(1, 13):
        curr_r = ((l_idx + (h - 1) - 1) % 12) + 1
        rx, ry = r_c[h]
        ax.text(rx, ry, str(curr_r), fontsize=9, fontweight='bold', color='#8e24aa', ha='center', va='center')
        p_list = p_by_h[h]
        if p_list:
            px, py = p_c[h]
            txt = ("ASC\n" if h==1 else "") + "\n".join(p_list)
            ax.text(px, py, txt, fontsize=10, fontweight='bold', color='#263238', ha='center', va='center')
    return fig

def create_pdf(chart_fig, roadmap_text):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []
    
    img_buf = io.BytesIO()
    chart_fig.savefig(img_buf, format='png', bbox_inches='tight', dpi=150)
    img_buf.seek(0)
    elements.append(Image(img_buf, 4*inch, 4*inch))
    
    for line in roadmap_text.split('\n'):
        if line.strip():
            clean = line.replace('**', '').replace('##', '').replace('###', '').strip()
            elements.append(Paragraph(clean, styles['Normal']))
    doc.build(elements)
    buf.seek(0)
    return buf

# ==========================================
# 3. UI & AI LOGIC
# ==========================================

st.set_page_config(page_title="Vedic-Nutrigenetic AI", page_icon="🧬")
st.title("🧬 Vedic-Nutrigenetic Analysis Engine")

with st.sidebar:
    st.header("⚙️ Configuration")
    api_key = st.text_input("Gemini API Key", type="password")

col1, col2 = st.columns(2)
with col1:
    dob = st.date_input("DOB", value=datetime.date(1990, 8, 15))
    city = st.text_input("City", value="Patiala")
with col2:
    time_str = st.text_input("Time (HH:MM)", value="10:30")
    timezone = st.selectbox("TZ", ["Asia/Kolkata", "UTC", "America/New_York"])

st.subheader("🛡️ Biological Resilience")
c1, c2 = st.columns(2)
with c1:
    antiox = st.checkbox("High Antioxidant Intake")
with c2:
    snps = st.multiselect("Known SNPs", ["SOD2 Efficient", "ACE I/I", "MTHFR Normal"])

if st.button("Generate Report"):
    if not api_key: st.error("Please enter API Key in sidebar")
    else:
        try:
            with st.spinner("Analyzing..."):
                lat, lon = get_coordinates(city)
                if not lat: st.error("City not found"); st.stop()
                
                h, m = map(int, time_str.split(':'))
                matrix = generate_natal_matrix(dob.year, dob.month, dob.day, h, m, lat, lon, timezone)
                
                # Visuals
                fig = draw_north_indian_chart(matrix)
                st.pyplot(fig)
                
                # AI Logic
                client = genai.Client(api_key=api_key)
                prompt = f"Expert PhD Nutrigenetics and Vedic analysis for matrix: {json.dumps(matrix)}. Use Bhagavad Gita and Chanakya Niti. Cite science papers."
                res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                
                st.markdown(res.text)
                
                pdf = create_pdf(fig, res.text)
                st.download_button("Download PDF", data=pdf, file_name="Roadmap.pdf", mime="application/pdf")
        except Exception as e:
            st.error(f"Critical Error: {e}")
