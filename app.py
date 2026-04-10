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
# 1. CORE MATH & DASHAS
# ==========================================

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
DASHA_ORDER = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
DASHA_YRS = {"Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7, "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17}

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

def get_detailed_dasha(moon_lon, dob):
    """Calculates Mahadasha and Antardasha for grounding the AI."""
    # Total cycle 120 years
    nak_span = 360/27
    nak_idx = int(moon_lon / nak_span)
    # Starting Lord
    start_lord_idx = nak_idx % 9
    
    # Calculate balance at birth
    rem_in_nak = ( (nak_idx + 1) * nak_span ) - moon_lon
    perc_rem = rem_in_nak / nak_span
    
    # Time passed since birth
    now = datetime.datetime.now()
    diff = now.year - dob.year + (now.month - dob.month)/12.0
    
    # Find current Mahadasha
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

    # Find current Antardasha within Mahadasha
    m_total = DASHA_YRS[m_lord]
    time_into_m = diff - m_start
    
    a_idx = DASHA_ORDER.index(m_lord)
    a_elapsed = 0
    for i in range(9):
        current_a_lord = DASHA_ORDER[(a_idx + i) % 9]
        # Antardasha span = (M_yrs * A_yrs) / 120
        a_span = (m_total * DASHA_YRS[current_a_lord]) / 120.0
        if a_elapsed + a_span > time_into_m:
            return {"Mahadasha": m_lord, "Antardasha": current_a_lord, "YearsIntoM": round(time_into_m, 2)}
        a_elapsed += a_span
    return {"Mahadasha": m_lord, "Antardasha": "Unknown"}

# ==========================================
# 2. CALCULATION ENGINE
# ==========================================

def get_coords(city):
    geolocator = Nominatim(user_agent="iron_primer_v15")
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
        return data
    except Exception as e: return f"ERROR: {str(e)}"

# ==========================================
# 3. VISUALIZATION
# ==========================================

def draw_chart(data, title="Natal Chart"):
    p_by_h = {i: [] for i in range(1, 13)}
    l_idx = SIGNS.index(data["Ascendant"]["Sign"]) + 1
    for b, d in data.items():
        if b not in ["Ascendant", "DashaLevels"]: p_by_h[d["House"]].append(b[:3] if b not in ["Rahu", "Ketu"] else b)
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
# 4. STREAMLIT UI & AI LOGIC
# ==========================================

st.set_page_config(page_title="Iron Primer Expert Engine", page_icon="🧘")
st.title("🧘 Vedic Life, Professional & Progeny Engine")

with st.sidebar:
    st.header("🔑 Engine Access")
    groq_key = st.text_input("Groq API Key", type="password")
    mode = st.radio("Select Mode", ["Individual Research Analysis", "Marriage & Progeny Analysis"])

st.subheader("👤 Individual 1 Details")
c1, c2 = st.columns(2)
with c1:
    dob1 = st.text_input("Date (DD-MM-YYYY)", value="15-08-1990", key="d1")
    city1 = st.text_input("City", value="Patiala", key="c1")
with c2:
    tob1 = st.text_input("Time (HH:MM)", value="10:30", key="t1")
    tz1 = st.selectbox("Timezone", ["Asia/Kolkata", "UTC"], key="z1")

if mode == "Marriage & Progeny Analysis":
    st.markdown("---")
    st.subheader("👥 Individual 2 Details")
    cc1, cc2 = st.columns(2)
    with cc1:
        dob2 = st.text_input("Date (DD-MM-YYYY)", value="01-01-1992", key="d2")
        city2 = st.text_input("City", value="Chandigarh", key="c2")
    with cc2:
        tob2 = st.text_input("Time (HH:MM)", value="14:15", key="t2")
        tz2 = st.selectbox("Timezone", ["Asia/Kolkata", "UTC"], key="z2")

if st.button("Generate Professional Analysis"):
    if not groq_key: st.error("Please add Groq API Key.")
    else:
        with st.spinner("Processing deep celestial cycles..."):
            d1 = calculate_chart(dob1, tob1, city1, tz1)
            if isinstance(d1, str): st.error(f"P1 Error: {d1}"); st.stop()
            
            figs = [draw_chart(d1, "Individual 1 Chart")]
            prompt_ctx = f"P1 Data: {json.dumps(d1)}"
            
            if mode == "Marriage & Progeny Analysis":
                d2 = calculate_chart(dob2, tob2, city2, tz2)
                if isinstance(d2, str): st.error(f"P2 Error: {d2}"); st.stop()
                figs.append(draw_chart(d2, "Individual 2 Chart"))
                prompt_ctx += f"\nP2 Data: {json.dumps(d2)}"
            
            for f in figs: st.pyplot(f)
            
            # --- AI SYNTHESIS WITH DASHAS & DEPTH ---
            client = Groq(api_key=groq_key)
            prompt = f"""
            Analyze as a PhD Researcher & Vedic Expert. Data Context: {prompt_ctx}. Current Date: {datetime.datetime.now()}.
            
            INSTRUCTIONS:
            1. **Vimshottari Dasha Analysis:** Provide a sequential analysis considering Mahadasha, Antardasha, and extrapolate Pratyantar, Sookshm, and Prana dashas based on the current date for the individual(s). Explain how these overlapping cycles affect current life events.
            2. **Marriage Life Depth:** - Detailed 7th house and its lord analysis.
               - Check for Mangal Dosha (Kuja Dosha) and its cancellation.
               - Stability index based on 'Bhakoot' and 'Gana' themes.
            3. **Children (Progeny) Depth:**
               - 5th House (Santana Sthan) lord strength.
               - Role of Jupiter (Putrakaraka). 
               - Discuss themes of the Saptamsha (D7) potential and timing of progeny during the current dasha cycles.
            4. **Professional & Clinical:** karmic career path (10th house) and physiological vulnerabilities (6/8/12).
            5. **Citations & Wisdom:** Back behavioral/clinical claims with literature (Author, Year). Integrate Bhagavad Gita (18.14) and Chanakya Niti.
            """
            
            try:
                completion = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.6,
                    max_tokens=4000
                )
                final_report = completion.choices[0].message.content
                st.markdown("---")
                st.markdown(final_report)
                
                # PDF Generation
                buf = io.BytesIO(); doc = SimpleDocTemplate(buf, pagesize=A4); styles = getSampleStyleSheet(); elements = []
                for f in figs:
                    ib = io.BytesIO(); f.savefig(ib, format='png'); ib.seek(0)
                    elements.append(Image(ib, 3.5*inch, 3.5*inch))
                elements.append(Spacer(1, 20))
                elements.append(Paragraph(final_report.replace('\n', '<br/>'), styles['Normal']))
                doc.build(elements)
                st.download_button("📥 Download PhD Report", data=buf.getvalue(), file_name="Roadmap.pdf", mime="application/pdf")
            except Exception as e: st.error(f"Groq API Error: {e}")
