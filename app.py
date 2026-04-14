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
from geopy.geocoders import Nominatim
import io
import time

# PDF Generation
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

# ==========================================
# 1. SCIENTIFIC-VEDIC CONSTANTS & NAKSHATRAS
# ==========================================

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
DASHA_ORDER = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
DASHA_YRS = {"Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7, "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17}
NAKSHATRAS = ["Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra", "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"]

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

def get_nakshatra_pada(lon):
    """Calculates exact Nakshatra and Pada (1-4) for precise Guna Milan."""
    nak_span = 360 / 27
    pada_span = nak_span / 4
    nak_idx = int(lon / nak_span)
    rem = lon % nak_span
    pada = int(rem / pada_span) + 1
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
# 3. ASTRONOMICAL CALCULATION
# ==========================================

def get_coords(city):
    geolocator = Nominatim(user_agent="iron_primer_v18_deep")
    try:
        location = geolocator.geocode(city, timeout=10)
        return (location.latitude, location.longitude) if location else (None, None)
    except: return (None, None)

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
        data["Moon_Details"] = get_nakshatra_pada(data["Moon"]["Lon"]) # CRITICAL for Ashtakoota
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
# 5. STREAMLIT CORE UI
# ==========================================

st.set_page_config(page_title="Iron Primer PhD Engine", page_icon="🧬", layout="wide")
st.title("🧬 Scientific-Vedic Bilingual Deep Engine")
st.markdown("---")

with st.sidebar:
    st.header("🔑 Engine Access")
    groq_key = st.text_input("Groq API Key", type="password")
    mode = st.radio("Select Analysis Protocol", ["Individual Bio-Audit", "Marriage & Progeny Sync"])
    st.info("High-Precision Mode: Exhaustive Details Enabled")

c1, c2 = st.columns(2)
with c1:
    st.subheader("👤 Individual 1")
    dob1 = st.text_input("Birth Date (DD-MM-YYYY)", value="15-08-1990", key="d1")
    city1 = st.text_input("Birth City", value="Patiala", key="c1")
    tob1 = st.text_input("Birth Time (HH:MM)", value="10:30", key="t1")
    tz1 = st.selectbox("Local Timezone", ["Asia/Kolkata", "UTC", "America/New_York"], key="z1")

if mode == "Marriage & Progeny Sync":
    with c2:
        st.subheader("👥 Partner Individual")
        dob2 = st.text_input("Birth Date (DD-MM-YYYY)", value="01-01-1992", key="d2")
        city2 = st.text_input("Birth City", value="Chandigarh", key="c2")
        tob2 = st.text_input("Birth Time (HH:MM)", value="14:15", key="t2")
        tz2 = st.selectbox("Local Timezone", ["Asia/Kolkata", "UTC"], key="z2")

if st.button("🚀 Generate Exhaustive Multilingual Report"):
    if not groq_key: st.error("Add Groq API Key.")
    else:
        with st.spinner("Calculating Sub-Divisional Arrays and Guna Milan..."):
            d1 = calculate_chart(dob1, tob1, city1, tz1)
            if isinstance(d1, str): st.error(f"P1: {d1}"); st.stop()
            
            figs = [draw_chart(d1, "Individual 1 Celestial Matrix")]
            prompt_ctx = f"P1 Data: {json.dumps(d1)}"
            
            if mode == "Marriage & Progeny Sync":
                d2 = calculate_chart(dob2, tob2, city2, tz2)
                if isinstance(d2, str): st.error(f"P2: {d2}"); st.stop()
                figs.append(draw_chart(d2, "Partner Celestial Matrix"))
                prompt_ctx += f"\nP2 Data: {json.dumps(d2)}"
            
            cc1, cc2 = st.columns(2)
            with cc1: st.pyplot(figs[0])
            if len(figs) > 1:
                with cc2: st.pyplot(figs[1])
            
            client = Groq(api_key=groq_key)
            prompt = f"""
            Role: PhD Research Scientist & Vedic Astrologer (Persona: The Iron Primer).
            Current Date: {datetime.datetime.now()}. Matrix: {prompt_ctx}. Mode: {mode}.
            
            CRITICAL MULTILINGUAL INSTRUCTION:
            Generate EXHAUSTIVE, multi-page level detail in English first.
            Then type EXACTLY this delimiter on a new line: ===HINDI_START===
            Then provide the EXACT same exhaustive detail translated into professional Hindi.
            DO NOT truncate. Write at least 1500 words per language.

            ANALYSIS REQUIREMENTS (Extreme Depth Required):
            1. **ASHTAKOOTA MILAN (For Marriage Mode ONLY):** You MUST calculate and output the exact points out of 36 (Guna Milan) using the provided Moon Nakshatras and Signs. Explicitly break down the score for: Varna (1), Vashya (2), Tara (3), Yoni (4), Graha Maitri (5), Gana (6), Bhakoot (7), and Nadi (8). Explain Nadi and Bhakoot dosha if present.
            2. **Minute-to-Minute Marriage Analysis:** Do not just say "good or bad". Analyze the 7th Lord conjunctions, aspects, Mangal Dosha (and its cancellations), and Navamsha (D9) potential for psychological synchrony. 
            3. **Deep Progeny Vitality:** Analyze the 5th House, 5th Lord, Jupiter, and explicitly discuss Saptamsha (D7) themes. Give the potential timing of progeny based on current Vimshottari Mahadasha/Antardasha.
            4. **Bio-Celestial Blueprint:** Deep physiological vulnerabilities using Houses 6/8/12. Give precise 'Sattvic' nutrition to balance specific elements (Agni/Vata/Kapha).
            5. **Professional Karma:** Exact cognitive skillset mapped to 10th House.
            6. **Citations:** Back health/psychological claims with (Author, Year). Use Bhagavad Gita and Chanakya Niti.
            """
            
            try:
                # Max tokens cranked to 8000 to ensure the deep-dive doesn't get cut off
                completion = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.6, 
                    max_tokens=8000
                )
                report = completion.choices[0].message.content
                
                st.markdown("---")
                
                if "===HINDI_START===" in report:
                    eng_text, hin_text = report.split("===HINDI_START===")
                    tab1, tab2 = st.tabs(["🇬🇧 Exhaustive English Analysis", "🇮🇳 विस्तृत हिंदी विश्लेषण (Hindi)"])
                    with tab1: st.markdown(eng_text.strip())
                    with tab2: st.markdown(hin_text.strip())
                    
                    download_str = f"# ENGLISH REPORT\n\n{eng_text.strip()}\n\n---\n\n# HINDI REPORT\n\n{hin_text.strip()}"
                else:
                    st.markdown(report)
                    download_str = report

                file_bytes = download_str.encode('utf-8')
                st.download_button(
                    label="📥 Download Full In-Depth Report (Markdown)", 
                    data=file_bytes, 
                    file_name="Deep_Bio_Audit_Report.md", 
                    mime="text/markdown"
                )
                
            except Exception as e: st.error(f"Groq API Error: {e}")
