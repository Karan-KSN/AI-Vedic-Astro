import streamlit as st
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import swisseph as swe
import datetime
import pytz
from groq import Groq
import json
from geopy.geocoders import Nominatim, ArcGIS
import io
import time
import os
import urllib.request
import re

# PDF Generation
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import inch

# ==========================================
# 0. HINDI PDF FONT ENGINE
# ==========================================
def setup_hindi_font():
    """Downloads and registers a Google Font for Hindi PDF rendering to prevent crashes."""
    font_path = "NotoSansDevanagari-Regular.ttf"
    font_url = "https://raw.githubusercontent.com/googlefonts/noto-fonts/main/unhinted/ttf/NotoSansDevanagari/NotoSansDevanagari-Regular.ttf"
    
    if not os.path.exists(font_path):
        try:
            urllib.request.urlretrieve(font_url, font_path)
        except Exception as e:
            return False
    try:
        pdfmetrics.registerFont(TTFont('HindiFont', font_path))
        return True
    except:
        return False

def format_text_for_pdf(text):
    """Converts basic Markdown to ReportLab XML format."""
    text = text.replace('<', '&lt;').replace('>', '&gt;')
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text) # Convert bold
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)     # Convert italics
    text = re.sub(r'#(.*?)\n', r'<b>\1</b>\n', text)    # Convert headers
    return text

# ==========================================
# 1. SCIENTIFIC-VEDIC CONSTANTS & NAKSHATRAS
# ==========================================
SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
DASHA_ORDER = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
DASHA_YRS = {"Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7, "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17}
NAKSHATRAS = ["Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra", "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"]

def get_planet_dignity(planet, sign):
    dignities = {
        "Sun": {"Ex": "Aries", "Deb": "Libra"}, "Moon": {"Ex": "Taurus", "Deb": "Scorpio"},
        "Mars": {"Ex": "Capricorn", "Deb": "Cancer"}, "Mercury": {"Ex": "Virgo", "Deb": "Pisces"},
        "Jupiter": {"Ex": "Cancer", "Deb": "Capricorn"}, "Venus": {"Ex": "Pisces", "Deb": "Virgo"},
        "Saturn": {"Ex": "Libra", "Deb": "Aries"}
    }
    if planet in dignities:
        if sign == dignities[planet]["Ex"]: return "Exalted (Uchcha)"
        if sign == dignities[planet]["Deb"]: return "Debilitated (Neecha)"
    return "Neutral"

def get_nakshatra_pada(lon):
    nak_span = 360 / 27; pada_span = nak_span / 4
    nak_idx = int(lon / nak_span)
    pada = int((lon % nak_span) / pada_span) + 1
    return {"Nakshatra": NAKSHATRAS[nak_idx], "Pada": pada}

# ==========================================
# 2. TEMPORAL PRECISION ENGINE (DASHAS)
# ==========================================
def get_detailed_dasha(moon_lon, dob):
    nak_span = 360/27
    nak_idx = int(moon_lon / nak_span)
    start_lord_idx = nak_idx % 9
    rem_in_nak = ((nak_idx + 1) * nak_span) - moon_lon
    perc_rem = rem_in_nak / nak_span
    now = datetime.datetime.now()
    diff = now.year - dob.year + (now.month - dob.month)/12.0
    curr_idx = start_lord_idx
    balance = perc_rem * DASHA_YRS[DASHA_ORDER[curr_idx]]
    
    elapsed = 0
    if diff < balance:
        m_lord = DASHA_ORDER[curr_idx]
        m_start = 0
    else:
        elapsed = balance
        curr_idx = (curr_idx + 1) % 9
        while elapsed + DASHA_YRS[DASHA_ORDER[curr_idx]] < diff:
            elapsed += DASHA_YRS[DASHA_ORDER[curr_idx]]
            curr_idx = (curr_idx + 1) % 9
        m_lord = DASHA_ORDER[curr_idx]
        m_start = elapsed

    m_total = DASHA_YRS[m_lord]
    time_into_m = diff - m_start
    a_idx = DASHA_ORDER.index(m_lord)
    a_elapsed = 0
    for i in range(9):
        current_a_lord = DASHA_ORDER[(a_idx + i) % 9]
        a_span = (m_total * DASHA_YRS[current_a_lord]) / 120.0
        if a_elapsed + a_span > time_into_m:
            return {"Mahadasha": m_lord, "Antardasha": current_a_lord, "Progress": f"{round((time_into_m/m_total)*100, 1)}%"}
        a_elapsed += a_span
    return {"Mahadasha": m_lord, "Antardasha": "Transitioning"}

# ==========================================
# 3. ROBUST ASTRONOMICAL CALCULATION
# ==========================================
def get_coords(city):
    """3-Tier Geocoder: Local DB -> ArcGIS -> Nominatim (Solves CITY_ERR)"""
    city_clean = city.lower().strip()
    local_db = {
        "patiala": (30.3398, 76.3869), "chandigarh": (30.7333, 76.7794),
        "mohali": (30.7046, 76.7179), "sangrur": (30.2458, 75.8421),
        "ludhiana": (30.9009, 75.8572), "jalandhar": (31.3260, 75.5761),
        "amritsar": (31.6340, 74.8723), "new delhi": (28.6139, 77.2090),
        "delhi": (28.6139, 77.2090), "mumbai": (19.0760, 72.8777)
    }
    if city_clean in local_db: return local_db[city_clean]
        
    try:
        arc = ArcGIS(timeout=10)
        loc = arc.geocode(city)
        if loc: return (loc.latitude, loc.longitude)
    except: pass

    try:
        nom = Nominatim(user_agent="iron_primer_v21", timeout=10)
        loc = nom.geocode(city)
        if loc: return (loc.latitude, loc.longitude)
    except: pass
    
    return (None, None)

def calculate_chart(dob_str, time_str, city, tz):
    try:
        y, m, d = map(int, dob_str.split('-')[::-1])
        h, mn = map(int, time_str.split(':'))
        lat, lon = get_coords(city)
        if not lat: return "CITY_ERR"
        
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
        
        data["Ketu"] = {"Sign": SIGNS[int(((data["Rahu"]["Lon"] + 180) % 360)/30)], "Deg": round((data["Rahu"]["Lon"] + 180) % 30, 2), "Lon": (data["Rahu"]["Lon"] + 180) % 360, "Dignity": "Neutral"}
        houses, ascmc = swe.houses_ex(jd, lat, lon, b'P', flags)
        asc_sign = SIGNS[int(ascmc[0]/30)]
        data["Ascendant"] = {"Sign": asc_sign, "Deg": round(ascmc[0]%30, 2)}
        
        a_idx = SIGNS.index(asc_sign)
        for b in data:
            if b != "Ascendant":
                p_idx = SIGNS.index(data[b]["Sign"])
                data[b]["House"] = ((p_idx - a_idx) % 12) + 1
                
        data["DashaLevels"] = get_detailed_dasha(data["Moon"]["Lon"], datetime.date(y, m, d))
        data["Moon_Details"] = get_nakshatra_pada(data["Moon"]["Lon"])
        return data
    except Exception as e: return f"ERROR: {str(e)}"

# ==========================================
# 4. DASHBOARD VISUALIZATION
# ==========================================
def draw_chart(data, title="Celestial Matrix"):
    p_by_h = {i: [] for i in range(1, 13)}
    l_idx = SIGNS.index(data["Ascendant"]["Sign"]) + 1
    for b, d in data.items():
        if b not in ["Ascendant", "DashaLevels", "Moon_Details"]: p_by_h[d["House"]].append(b[:3] if b not in ["Rahu", "Ketu"] else b)
    fig, ax = plt.subplots(figsize=(5, 5), facecolor='#fdfcf5')
    ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis('off')
    lp = {'color': '#2c3e50', 'linewidth': 2}
    ax.add_patch(patches.Rectangle((0, 0), 10, 10, fill=False, **lp))
    ax.plot([0, 10], [0, 10], **lp); ax.plot([0, 10], [10, 0], **lp)
    ax.plot([5, 0, 5, 10, 5], [10, 5, 0, 5, 10], **lp)
    rc = {1:(5,5.3), 2:(0.3,9.5), 3:(0.3,5.3), 4:(4.7,5.3), 5:(0.3,4.3), 6:(0.3,0.3), 7:(5,4.3), 8:(9.7,0.3), 9:(9.7,4.3), 10:(5.3,5.3), 11:(9.7,5.3), 12:(9.7,9.5)}
    pc = {1:(5,7.5), 2:(2.5,8.8), 3:(1.2,7.5), 4:(2.5,6.2), 5:(1.2,2.5), 6:(2.5,1.2), 7:(5,2.5), 8:(7.5,1.2), 9:(8.8,2.5), 10:(7.5,6.2), 11:(8.8,7.5), 12:(7.5,8.8)}
    for h in range(1, 13):
        curr_r = ((l_idx + (h - 1) - 1) % 12) + 1
        ax.text(rc[h][0], rc[h][1], str(curr_r), fontsize=8, fontweight='bold', color='#c0392b', ha='center')
        if p_by_h[h]:
            txt = ("ASC\n" if h==1 else "") + "\n".join(p_by_h[h])
            ax.text(pc[h][0], pc[h][1], txt, fontsize=9, fontweight='bold', color='#34495e', ha='center', va='center')
    plt.title(title, fontsize=12, pad=15, fontweight='bold')
    return fig

# ==========================================
# 5. STREAMLIT CORE UI & PDF EXPORT
# ==========================================
st.set_page_config(page_title="Iron Primer PhD Engine", page_icon="🧬", layout="wide")
st.title("🧬 Scientific-Vedic Bilingual Engine (V21)")
st.markdown("---")

with st.sidebar:
    st.header("🔑 Engine Access")
    groq_key = st.text_input("Groq API Key", type="password")
    mode = st.radio("Select Analysis Protocol", ["Individual Bio-Audit", "Marriage & Progeny Sync"])

c1, c2 = st.columns(2)
with c1:
    st.subheader("👤 Individual 1")
    dob1 = st.text_input("Birth Date (DD-MM-YYYY)", value="15-08-1990", key="d1")
    city1 = st.text_input("Birth City", value="Sangrur", key="c1")
    tob1 = st.text_input("Birth Time (HH:MM)", value="10:30", key="t1")
    tz1 = st.selectbox("Local Timezone", ["Asia/Kolkata", "UTC", "America/New_York"], key="z1")

if mode == "Marriage & Progeny Sync":
    with c2:
        st.subheader("👥 Partner Individual")
        dob2 = st.text_input("Birth Date (DD-MM-YYYY)", value="01-01-1992", key="d2")
        city2 = st.text_input("Birth City", value="Chandigarh", key="c2")
        tob2 = st.text_input("Birth Time (HH:MM)", value="14:15", key="t2")
        tz2 = st.selectbox("Local Timezone", ["Asia/Kolkata", "UTC"], key="z2")

if st.button("🚀 Generate PDF & Dashboard Report"):
    if not groq_key: st.error("Add Groq API Key.")
    else:
        with st.spinner("Calculating Arrays & Generating English Analytics..."):
            d1 = calculate_chart(dob1, tob1, city1, tz1)
            if d1 == "CITY_ERR": st.error(f"❌ Could not locate city: {city1}."); st.stop()
            
            figs = [draw_chart(d1, "Individual Celestial Matrix")]
            prompt_ctx = f"P1 Data: {json.dumps(d1)}"
            
            if mode == "Marriage & Progeny Sync":
                d2 = calculate_chart(dob2, tob2, city2, tz2)
                if d2 == "CITY_ERR": st.error(f"❌ Could not locate city: {city2}."); st.stop()
                figs.append(draw_chart(d2, "Partner Celestial Matrix"))
                prompt_ctx += f"\nP2 Data: {json.dumps(d2)}"
            
            cc1, cc2 = st.columns(2)
            with cc1: st.pyplot(figs[0])
            if len(figs) > 1:
                with cc2: st.pyplot(figs[1])
            
            client = Groq(api_key=groq_key)
            
            # --- SPLIT PROMPT ARCHITECTURE ---
            if mode == "Individual Bio-Audit":
                eng_prompt = f"""
                Role: PhD Research Scientist & Vedic Astrologer. Date: {datetime.datetime.now()}. Matrix: {prompt_ctx}. Mode: {mode}.
                
                Write an EXHAUSTIVE English report (minimum 1500 words) focusing STRICTLY on this single individual. DO NOT mention matchmaking, Guna Milan, or partner compatibility.
                
                1. **Bio-Celestial Blueprint (Health):** Analyze Houses 1/6/8/12. Detail physiological vulnerabilities, Agni/Vata/Kapha balance, and precise Sattvic nutrition.
                2. **Professional Karma & Wealth:** Analyze 2nd, 10th, and 11th Houses. Detail cognitive skillset, wealth accumulation patterns, and career trajectory.
                3. **Psychological & Dharma Matrix:** Analyze the Moon, 4th House (inner peace), and 9th House (Dharma/Luck). 
                4. **Dasha Extrapolation:** Use the provided Mahadasha/Antardasha to calculate precise Pratyantar, Sookshm, and Prana timing for current life events.
                5. **Citations & Wisdom:** Back claims with scientific literature (Author, Year). Use Bhagavad Gita and Chanakya Niti for strategic life advice.
                """
            else:
                eng_prompt = f"""
                Role: PhD Research Scientist & Vedic Astrologer. Date: {datetime.datetime.now()}. Matrix: {prompt_ctx}. Mode: {mode}.
                
                Write an EXHAUSTIVE English report (minimum 1500 words) for both individuals.
                1. **Ashtakoota Milan:** Break down the exact 36-point score using Nakshatras and Padas.
                2. **Minute-to-Minute Marriage:** 7th Lord, Navamsha (D9), Mangal Dosha and cancellations.
                3. **Progeny Vitality:** 5th House, Jupiter, Saptamsha (D7), and precise dasha timing for children.
                4. **Bio-Celestial Blueprint:** Houses 6/8/12 vulnerabilities and Sattvic nutrition for both.
                5. **Professional Karma:** 10th House skillset overview.
                6. **Citations:** Back claims with (Author, Year). Use Chanakya Niti for marital strategy.
                """
            
            try:
                eng_res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": eng_prompt}], temperature=0.6, max_tokens=5000)
                eng_text = eng_res.choices[0].message.content
                
                with st.spinner("Translating matrix into Academic Hindi..."):
                    hin_prompt = f"Translate the following report into highly accurate, fluent Hindi (हिंदी). Maintain all scientific formatting.\n\n{eng_text}"
                    hin_res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": hin_prompt}], temperature=0.3, max_tokens=6000)
                    hin_text = hin_res.choices[0].message.content

                st.markdown("---")
                tab1, tab2 = st.tabs(["🇬🇧 Exhaustive English", "🇮🇳 विस्तृत हिंदी विश्लेषण"])
                with tab1: st.markdown(eng_text.strip())
                with tab2: st.markdown(hin_text.strip())
                
                # --- NATIVE PDF COMPILER ---
                with st.spinner("Compiling Native PDF Document..."):
                    font_ready = setup_hindi_font()
                    buf = io.BytesIO()
                    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
                    styles = getSampleStyleSheet()
                    
                    eng_style = ParagraphStyle('English', parent=styles['Normal'], fontName='Helvetica', fontSize=10, spaceAfter=10)
                    if font_ready:
                        hin_style = ParagraphStyle('Hindi', parent=styles['Normal'], fontName='HindiFont', fontSize=11, spaceAfter=10, leading=16)
                    else:
                        hin_style = eng_style # Safety fallback
                        
                    elements = []
                    
                    for f in figs:
                        ib = io.BytesIO(); f.savefig(ib, format='png'); ib.seek(0)
                        elements.append(Image(ib, 3.5*inch, 3.5*inch))
                        elements.append(Spacer(1, 10))
                        
                    elements.append(Paragraph("<b>ENGLISH BIO-CELESTIAL REPORT</b>", styles['Heading1']))
                    clean_eng = format_text_for_pdf(eng_text)
                    for para in clean_eng.split('\n'):
                        if para.strip(): elements.append(Paragraph(para, eng_style))
                    
                    elements.append(Spacer(1, 30))
                    
                    elements.append(Paragraph("<b>HINDI REPORT (हिंदी विश्लेषण)</b>", styles['Heading1']))
                    clean_hin = format_text_for_pdf(hin_text)
                    for para in clean_hin.split('\n'):
                        if para.strip(): elements.append(Paragraph(para, hin_style))
                        
                    doc.build(elements)
                    
                    st.download_button(
                        label="📥 Download Bilingual PDF Report", 
                        data=buf.getvalue(), 
                        file_name="IronPrimer_Bio_Audit.pdf", 
                        mime="application/pdf"
                    )
                
            except Exception as e: st.error(f"Groq API / PDF Error: {e}")
