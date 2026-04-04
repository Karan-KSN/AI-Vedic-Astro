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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

# ==========================================
# 1. PAGE CONFIGURATION
# ==========================================
st.set_page_config(page_title="Vedic AI Roadmap", page_icon="✨", layout="wide")

st.title("✨ AI Vedic Astrology Roadmap")
st.markdown("Generate a precise visual chart and a professional PDF roadmap.")

with st.sidebar:
    st.header("⚙️ Configuration")
    api_key = st.text_input("Enter Google Gemini API Key:", type="password")
    st.info("Your key is processed in-memory and never stored.")

# ==========================================
# 2. CALCULATION & DRAWING ENGINES
# ==========================================

def get_coordinates(city_name):
    geolocator = Nominatim(user_agent="iron_primer_astrology_app")
    try:
        location = geolocator.geocode(city_name)
        return (location.latitude, location.longitude) if location else (None, None)
    except: return (None, None)

def get_zodiac_info(longitude):
    signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
    return signs[int(longitude / 30)], round(longitude % 30, 4)

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
    ketu_lon = (chart_data["Rahu"]["Total_Lon"] + 180) % 360
    k_sign, k_deg = get_zodiac_info(ketu_lon)
    chart_data["Ketu"] = {"Sign": k_sign, "Degree": k_deg, "Total_Lon": round(ketu_lon, 4)}
    houses, ascmc = swe.houses_ex(jd, lat, lon, b'P', flags)
    asc_sign, asc_deg = get_zodiac_info(ascmc[0])
    chart_data["Ascendant"] = {"Sign": asc_sign, "Degree": asc_deg, "Total_Lon": round(ascmc[0], 4)}
    signs_list = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
    lords = {"Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury", "Cancer": "Moon", "Leo": "Sun", "Virgo": "Mercury", "Libra": "Venus", "Scorpio": "Mars", "Sagittarius": "Jupiter", "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter"}
    asc_idx = signs_list.index(asc_sign)
    for b, d in chart_data.items():
        if b != "Ascendant":
            p_idx = signs_list.index(d["Sign"])
            chart_data[b]["House"] = ((p_idx - asc_idx) % 12) + 1
            chart_data[b]["Sign_Lord"] = lords[d["Sign"]]
    return chart_data

def draw_north_indian_chart(chart_data):
    rashi_names = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
    planets_by_house = {i: [] for i in range(1, 13)}
    lagna_rashi_num = rashi_names.index(chart_data["Ascendant"]["Sign"]) + 1
    for body, data in chart_data.items():
        if body != "Ascendant":
            short_name = body[:3] if body not in ["Rahu", "Ketu"] else body
            planets_by_house[data["House"]].append(short_name)
    fig, ax = plt.subplots(figsize=(6, 6), facecolor='#fdfcf5')
    ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis('off')
    line_params = {'color': '#4a4a4a', 'linewidth': 1.5}
    ax.add_patch(patches.Rectangle((0, 0), 10, 10, fill=False, **line_params))
    ax.plot([0, 10], [0, 10], **line_params); ax.plot([0, 10], [10, 0], **line_params)
    ax.plot([5, 0, 5, 10, 5], [10, 5, 0, 5, 10], **line_params)
    r_coords = {1: (5, 5.2), 2: (0.2, 9.4), 3: (0.2, 5.2), 4: (4.8, 5.2), 5: (0.2, 4.4), 6: (0.2, 0.2), 7: (5, 4.4), 8: (9.4, 0.2), 9: (9.4, 4.4), 10: (5.2, 5.2), 11: (9.4, 5.2), 12: (9.4, 9.4)}
    p_coords = {1: (5, 7.5), 2: (2.5, 8.8), 3: (1.2, 7.5), 4: (2.5, 6.2), 5: (1.2, 2.5), 6: (2.5, 1.2), 7: (5, 2.5), 8: (7.5, 1.2), 9: (8.8, 2.5), 10: (7.5, 6.2), 11: (8.8, 7.5), 12: (7.5, 8.8)}
    for h in range(1, 13):
        curr_r = ((lagna_rashi_num + (h - 1) - 1) % 12) + 1
        rx, ry = r_coords[h]
        ax.text(rx, ry, str(curr_r), fontsize=9, fontweight='bold', color='#8e24aa', ha='center', va='center')
        p_list = planets_by_house[h]
        if p_list:
            px, py = p_coords[h]
            txt = ("ASC\n" if h==1 else "") + "\n".join(p_list)
            ax.text(px, py, txt, fontsize=10, fontweight='bold', color='#263238', ha='center', va='center')
    return fig

# ==========================================
# 3. PDF GENERATION LOGIC
# ==========================================
def create_pdf(chart_fig, roadmap_text):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    
    # Custom Styles
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=18, spaceAfter=20, alignment=1)
    body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontSize=11, leading=14, spaceAfter=10)
    
    elements = []
    elements.append(Paragraph("Personalized AI Vedic Roadmap", title_style))
    
    # 1. Add Chart Image
    img_buf = io.BytesIO()
    chart_fig.savefig(img_buf, format='png', bbox_inches='tight', dpi=150)
    img_buf.seek(0)
    img = Image(img_buf, 4*inch, 4*inch)
    elements.append(img)
    elements.append(Spacer(1, 0.5*inch))
    
    # 2. Add AI Text (Convert Markdown-ish lines to PDF Paragraphs)
    for line in roadmap_text.split('\n'):
        if line.strip():
            # Basic markdown conversion
            clean_line = line.replace('**', '').replace('##', '').replace('###', '').strip()
            if line.startswith('##'):
                elements.append(Paragraph(clean_line, styles['Heading2']))
            elif line.startswith('###'):
                elements.append(Paragraph(clean_line, styles['Heading3']))
            else:
                elements.append(Paragraph(clean_line, body_style))
    
    doc.build(elements)
    buf.seek(0)
    return buf

# ==========================================
# 4. AI & UI INTERFACE
# ==========================================
def generate_life_roadmap(matrix_data, key):
    client = genai.Client(api_key=key)
    system_prompt = f"Act as an elite Vedic Astrologer. Analyze this JSON: {json.dumps(matrix_data)}. Provide a granular 12-house analysis followed by professional roadmap and philosophical anchors using Bhagavad Gita and Chanakya Niti. Use Markdown."
    response = client.models.generate_content(model='gemini-2.5-flash', contents=system_prompt)
    return response.text

col1, col2 = st.columns(2)
with col1:
    dob = st.date_input("DOB", value=datetime.date(1990, 8, 15))
    city = st.text_input("City", value="New Delhi")
with col2:
    time_str = st.text_input("Time (HH:MM)", value="10:30")
    timezone = st.selectbox("Timezone", ["Asia/Kolkata", "America/New_York", "UTC"])

if st.button("Analyze & Generate PDF", type="primary"):
    if not api_key: st.error("Add API Key")
    else:
        with st.spinner("Processing..."):
            lat, lon = get_coordinates(city)
            matrix = generate_natal_matrix(dob.year, dob.month, dob.day, int(time_str.split(':')[0]), int(time_str.split(':')[1]), lat, lon, timezone)
            
            # Display Chart
            fig = draw_north_indian_chart(matrix)
            st.pyplot(fig)
            
            # Generate & Display Text
            roadmap = generate_life_roadmap(matrix, api_key)
            st.markdown(roadmap)
            
            # Create PDF for Download
            pdf_buf = create_pdf(fig, roadmap)
            st.download_button(
                label="📥 Download Roadmap PDF",
                data=pdf_buf,
                file_name=f"Vedic_Roadmap_{dob}.pdf",
                mime="application/pdf"
            )
