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
# 1. CORE LOGIC
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

def get_coords(city):
    geolocator = Nominatim(user_agent="iron_primer_research_v9")
    try:
        location = geolocator.geocode(city, timeout=10)
        return (location.latitude, location.longitude) if location else (None, None)
    except: return (None, None)

def calculate_chart(dob_str, time_str, city, tz):
    try:
        y, m, d = map(int, dob_str.split('-')[::-1])
        h, mn = map(int, time_str.split(':'))
        lat, lon = get_coords(city)
        if not lat: return "LOC_ERROR"
        
        local_tz = pytz.timezone(tz)
        utc_dt = local_tz.localize(datetime.datetime(y, m, d, h, mn)).astimezone(pytz.utc)
        jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour + utc_dt.minute / 60.0)
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        flags = swe.FLG_SIDEREAL | swe.FLG_SWIEPH
        
        planets = {"Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS, "Mercury": swe.MERCURY, "Jupiter": swe.JUPITER, "Venus": swe.VENUS, "Saturn": swe.SATURN, "Rahu": swe.TRUE_NODE}
        data = {}
        for name, p_id in planets.items():
            res, _ = swe.calc_ut(jd, p_id, flags)
            sign = SIGNS[int(res[0] / 30)]
            data[name] = {"Sign": sign, "Deg": round(res[0]%30, 2), "Lon": res[0], "Dignity": get_planet_dignity(name, sign)}
        
        data["Ketu"] = {"Sign": SIGNS[int(((data["Rahu"]["Lon"] + 180) % 360)/30)], "Deg": round((data["Rahu"]["Lon"] + 180) % 30, 2), "Lon": (data["Rahu"]["Lon"] + 180) % 360}
        houses, ascmc = swe.houses_ex(jd, lat, lon, b'P', flags)
        asc_sign = SIGNS[int(ascmc[0]/30)]
        data["Ascendant"] = {"Sign": asc_sign, "Deg": round(ascmc[0]%30, 2)}
        
        a_idx = SIGNS.index(asc_sign)
        for b in data:
            if b != "Ascendant":
                p_idx = SIGNS.index(data[b]["Sign"])
                data[b]["House"] = ((p_idx - a_idx) % 12) + 1
        return data
    except Exception as e: return f"ERROR: {str(e)}"

# ==========================================
# 2. UI & VISUALIZATION
# ==========================================

def draw_chart(data, title="Birth Chart"):
    p_by_h = {i: [] for i in range(1, 13)}
    l_idx = SIGNS.index(data["Ascendant"]["Sign"]) + 1
    for b, d in data.items():
        if b != "Ascendant": p_by_h[d["House"]].append(b[:3] if b not in ["Rahu", "Ketu"] else b)
    
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
    plt.title(title, fontsize=12)
    return fig

# ==========================================
# 3. MAIN APP
# ==========================================

st.set_page_config(page_title="Iron Primer PhD Engine", page_icon="🧬")
st.title("🧬 Vedic Clinical & Marriage Engine")

with st.sidebar:
    st.header("🔑 Config")
    api_key = st.text_input("Gemini API Key", type="password")
    mode = st.radio("Mode", ["Individual Health", "Marriage Longevity"])

st.subheader("👤 Details")
c1, c2 = st.columns(2)
with c1:
    dob1 = st.text_input("Date (DD-MM-YYYY)", value="15-08-1990", key="d1")
    city1 = st.text_input("Birth City", value="Patiala", key="c1")
with c2:
    tob1 = st.text_input("Time (HH:MM)", value="10:30", key="t1")
    tz1 = st.selectbox("Timezone", ["Asia/Kolkata", "UTC"], key="z1")

data2 = None
if mode == "Marriage Longevity":
    st.markdown("---")
    st.subheader("👥 Partner Details")
    cc1, cc2 = st.columns(2)
    with cc1:
        dob2 = st.text_input("Date (DD-MM-YYYY)", value="01-01-1992", key="d2")
        city2 = st.text_input("Birth City", value="Chandigarh", key="c2")
    with cc2:
        tob2 = st.text_input("Time (HH:MM)", value="14:15", key="t2")
        tz2 = st.selectbox("Timezone", ["Asia/Kolkata", "UTC"], key="z2")

if st.button("Generate Professional Roadmap"):
    if not api_key: st.error("Add API Key.")
    else:
        try:
            with st.spinner("Calculating Celestial Matrix..."):
                d1 = calculate_chart(dob1, tob1, city1, tz1)
                if isinstance(d1, str): st.error(d1); st.stop()
                
                figs = [draw_chart(d1, "Individual 1 Chart")]
                ctx_data = f"P1: {json.dumps(d1)}"
                
                if mode == "Marriage Longevity":
                    d2 = calculate_chart(dob2, tob2, city2, tz2)
                    if isinstance(d2, str): st.error(f"P2 Error: {d2}"); st.stop()
                    figs.append(draw_chart(d2, "Individual 2 Chart"))
                    ctx_data += f"\nP2: {json.dumps(d2)}"
                
                for f in figs: st.pyplot(f)
                
                # --- RESILIENT AI CALL ---
                client = genai.Client(api_key=api_key)
                prompt = f"""
                PhD Analysis for The Iron Primer. Data: {ctx_data}. Mode: {mode}.
                Tasks: 1. Clinical Predispositions (Houses 6,8,12). 2. 'Sattvic' nutrition based on planetary elements. 
                3. Marriage survival prediction & Stability Index. 4. Scientific citations (Author, Year). 
                5. Bhagavad Gita (18.14) & Chanakya Niti application.
                """
                
                report_text = ""
                placeholder = st.empty()
                
                # Try multiple times with increasing wait
                for attempt in range(5): 
                    try:
                        placeholder.info(f"Connecting to AI Engine (Attempt {attempt+1})...")
                        report = client.models.generate_content(model='gemini-1.5-flash', contents=prompt)
                        report_text = report.text
                        placeholder.empty()
                        break
                    except Exception as ai_e:
                        if "503" in str(ai_e) or "Unavailable" in str(ai_e):
                            wait_time = (attempt + 1) * 3
                            placeholder.warning(f"Server busy. Retrying in {wait_time}s...")
                            time.sleep(wait_time)
                        else:
                            st.error(f"AI Error: {ai_e}")
                            st.stop()
                
                if report_text:
                    st.markdown("---")
                    st.markdown(report_text)
                    
                    # PDF Creation
                    buf = io.BytesIO(); doc = SimpleDocTemplate(buf, pagesize=A4); styles = getSampleStyleSheet(); elements = []
                    for f in figs:
                        ib = io.BytesIO(); f.savefig(ib, format='png'); ib.seek(0)
                        elements.append(Image(ib, 3.5*inch, 3.5*inch))
                    elements.append(Spacer(1, 20))
                    elements.append(Paragraph(report_text.replace('\n', '<br/>'), styles['Normal']))
                    doc.build(elements)
                    st.download_button("📥 Download PDF Report", data=buf.getvalue(), file_name="Roadmap.pdf", mime="application/pdf")
                else:
                    st.error("Google servers are under high load. Please try again in 1 minute.")
                    
        except Exception as global_e: st.error(f"System Error: {global_e}")
