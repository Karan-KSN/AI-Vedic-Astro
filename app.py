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
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

# ==========================================
# 1. GLOBAL CONSTANTS & DIGNITY LOGIC
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
        if sign == dignities[planet]["Ex"]: return "Exalted (Uchcha)"
        if sign == dignities[planet]["Deb"]: return "Debilitated (Neecha)"
    return "Neutral"

# ==========================================
# 2. ASTRONOMICAL & DASHA ENGINES
# ==========================================

def get_coords(city):
    geo = Nominatim(user_agent="iron_primer_research_v4")
    try:
        loc = geo.geocode(city)
        return (loc.latitude, loc.longitude) if loc else (None, None)
    except: return (None, None)

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
    lord = nakshatras[idx][1]
    yrs = nakshatras[idx][2]
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

def calculate_chart(y, m, d, h, min_val, lat, lon, tz):
    local_tz = pytz.timezone(tz)
    l_time = local_tz.localize(datetime.datetime(y, m, d, h, min_val))
    utc = l_time.astimezone(pytz.utc)
    jd = swe.julday(utc.year, utc.month, utc.day, utc.hour + utc.minute / 60.0)
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    flags = swe.FLG_SIDEREAL | swe.FLG_SWIEPH
    
    planets = {"Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS, "Mercury": swe.MERCURY, "Jupiter": swe.JUPITER, "Venus": swe.VENUS, "Saturn": swe.SATURN, "Rahu": swe.TRUE_NODE}
    data = {}
    for name, p_id in planets.items():
        pos, _ = swe.calc_ut(jd, p_id, flags)
        sign = SIGNS[int(pos[0] / 30)]
        data[name] = {"Sign": sign, "Deg": round(pos[0]%30, 2), "Lon": pos[0], "Dignity": get_planet_dignity(name, sign)}
    
    data["Ketu"] = {"Sign": SIGNS[int(((data["Rahu"]["Lon"] + 180) % 360)/30)], "Deg": round(data["Rahu"]["Lon"] % 30, 2), "Lon": (data["Rahu"]["Lon"] + 180) % 360, "Dignity": "Neutral"}
    houses, ascmc = swe.houses_ex(jd, lat, lon, b'P', flags)
    asc_sign = SIGNS[int(ascmc[0]/30)]
    data["Ascendant"] = {"Sign": asc_sign, "Deg": round(ascmc[0]%30, 2)}
    
    a_idx = SIGNS.index(asc_sign)
    for b in data:
        if b != "Ascendant":
            p_idx = SIGNS.index(data[b]["Sign"])
            data[b]["House"] = ((p_idx - a_idx) % 12) + 1
    return data

# ==========================================
# 3. VISUALIZATION ENGINE
# ==========================================

def draw_chart(data):
    p_by_h = {i: [] for i in range(1, 13)}
    l_idx = SIGNS.index(data["Ascendant"]["Sign"]) + 1
    for b, d in data.items():
        if b != "Ascendant": p_by_h[d["House"]].append(b[:3] if b not in ["Rahu", "Ketu"] else b)
    
    fig, ax = plt.subplots(figsize=(6, 6), facecolor='#fdfcf5')
    ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis('off')
    lp = {'color': '#4a4a4a', 'linewidth': 2}
    ax.add_patch(patches.Rectangle((0, 0), 10, 10, fill=False, **lp))
    ax.plot([0, 10], [0, 10], **lp); ax.plot([0, 10], [10, 0], **lp)
    ax.plot([5, 0, 5, 10, 5], [10, 5, 0, 5, 10], **lp)
    
    rc = {1:(5,5.3), 2:(0.3,9.5), 3:(0.3,5.3), 4:(4.7,5.3), 5:(0.3,4.3), 6:(0.3,0.3), 7:(5,4.3), 8:(9.7,0.3), 9:(9.7,4.3), 10:(5.3,5.3), 11:(9.7,5.3), 12:(9.7,9.5)}
    pc = {1:(5,7.5), 2:(2.5,8.8), 3:(1.2,7.5), 4:(2.5,6.2), 5:(1.2,2.5), 6:(2.5,1.2), 7:(5,2.5), 8:(7.5,1.2), 9:(8.8,2.5), 10:(7.5,6.2), 11:(8.8,7.5), 12:(7.5,8.8)}
    
    for h in range(1, 13):
        curr_r = ((l_idx + (h - 1) - 1) % 12) + 1
        ax.text(rc[h][0], rc[h][1], str(curr_r), fontsize=10, fontweight='bold', color='#8e24aa', ha='center')
        if p_by_h[h]:
            txt = ("ASC\n" if h==1 else "") + "\n".join(p_by_h[h])
            ax.text(pc[h][0], pc[h][1], txt, fontsize=10, fontweight='bold', color='#263238', ha='center', va='center')
    return fig

# ==========================================
# 4. INTERFACE & CORE APP
# ==========================================

st.set_page_config(page_title="Iron Primer Research Engine", page_icon="🧬")
st.title("🧬 Vedic-Nutrigenetic Research Platform")

with st.sidebar:
    st.header("🔑 Authentication")
    api_key = st.text_input("Gemini API Key", type="password")

c1, c2 = st.columns(2)
with c1:
    dob_text = st.text_input("Date of Birth (DD-MM-YYYY)", value="15-08-1990", help="Use the format DD-MM-YYYY (e.g., 25-12-1985)")
    city = st.text_input("City of Birth", value="Patiala")
with c2:
    time_text = st.text_input("Time of Birth (HH:MM)", value="10:30", help="Use 24-hour format (e.g., 14:30 for 2:30 PM)")
    tz = st.selectbox("Timezone", ["Asia/Kolkata", "UTC", "America/New_York"])

st.subheader("🛡️ Resilience & Molecular Defense")
res_c1, res_c2 = st.columns(2)
with res_c1:
    diet = st.checkbox("High Antioxidant Intake (Nrf2 Path)")
    meditation = st.checkbox("Regulated Vagus Toning (Pranayama)")
with res_c2:
    snps = st.multiselect("Confirmed Genomic Markers", ["SOD2 Efficient", "ACE I/I", "MTHFR Normal"])

if st.button("Generate PhD Analysis"):
    if not api_key:
        st.error("⚠️ Enter Gemini API Key in sidebar.")
    else:
        try:
            # Date and Time Validation
            try:
                dob = datetime.datetime.strptime(dob_text, "%d-%m-%Y").date()
            except:
                st.error("❌ Invalid Date format. Use DD-MM-YYYY.")
                st.stop()
            
            try:
                h_val, m_val = map(int, time_text.split(':'))
            except:
                st.error("❌ Invalid Time format. Use HH:MM.")
                st.stop()

            with st.spinner("Analyzing Genomic & Celestial Inter-relations..."):
                lat, lon = get_coords(city)
                if not lat: st.error("City not found."); st.stop()
                
                matrix = calculate_chart(dob.year, dob.month, dob.day, h_val, m_val, lat, lon, tz)
                dasha = get_dasha_data(matrix["Moon"]["Lon"], dob)
                
                # Visuals
                fig = draw_chart(matrix)
                st.pyplot(fig)
                
                # AI Expert Synthesis
                client = genai.Client(api_key=api_key)
                prompt = f"""
                Elite PhD Analysis for: The Iron Primer.
                Current Matrix Data: {json.dumps(matrix)}
                Current Dasha: {dasha}
                Resilience Context: {json.dumps({'diet': diet, 'lifestyle': meditation, 'snps': snps})}
                
                REQUIREMENTS:
                1. 12-House detailed dispositor chain analysis.
                2. Nutrigenetics: Correlate planetary dignity with markers like ACE, SOD2, VDR. 
                   Cite specific scientific literature (Author, Year, Journal).
                3. Resilience Theory: Explain why some individuals experience transit-based oxidative stress while this user may be protected by their biological buffers.
                4. Wisdom: Synthesize advice using Bhagavad Gita (18.14) and Chanakya Niti.
                """
                report = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                st.markdown("---")
                st.markdown(report.text)
                
                # PDF Setup
                buf = io.BytesIO()
                doc = SimpleDocTemplate(buf, pagesize=A4)
                img_buf = io.BytesIO(); fig.savefig(img_buf, format='png'); img_buf.seek(0)
                elements = [Image(img_buf, 4*inch, 4*inch), Spacer(1, 20), Paragraph(report.text.replace('\n', '<br/>'), getSampleStyleSheet()['Normal'])]
                doc.build(elements)
                st.download_button("📥 Download Final PhD Report", data=buf.getvalue(), file_name=f"Roadmap_{dob}.pdf", mime="application/pdf")
                
        except Exception as e:
            st.error(f"System Error: {e}")
