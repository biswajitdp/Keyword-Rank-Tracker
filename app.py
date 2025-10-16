import os
import re
import time
import requests
import pandas as pd
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
import streamlit as st

# ------------------- ENV -------------------
load_dotenv()
SERP_API_KEY = os.getenv("SERPAPI_KEY")

# ------------------- DB --------------------
DB = "keywords.db"

def init_db():
    conn = sqlite3.connect(DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ranks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand_url TEXT,
            keyword TEXT,
            rank TEXT,
            country TEXT,
            lang TEXT,
            checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # ✅ Add missing column 'location' if not exists
    try:
        conn.execute("ALTER TABLE ranks ADD COLUMN location TEXT")
    except sqlite3.OperationalError:
        pass  # column already exists
    conn.close()

def save_rank(brand_url, keyword, rank, country, lang, location):
    conn = sqlite3.connect(DB)
    conn.execute(
        "INSERT INTO ranks (brand_url, keyword, rank, country, lang, location) VALUES (?, ?, ?, ?, ?, ?)",
        (brand_url, keyword, str(rank), country, lang, location)
    )
    conn.commit()
    conn.close()

def get_history():
    conn = sqlite3.connect(DB)
    df = pd.read_sql_query("SELECT * FROM ranks ORDER BY checked_at DESC", conn)
    conn.close()
    return df

init_db()

# ------------------- STATES & CITIES --------------------
INDIA_STATES_CITIES = {
    "Andhra Pradesh": ["Visakhapatnam", "Vijayawada", "Guntur", "Nellore", "Tirupati"],
    "Arunachal Pradesh": ["Itanagar", "Tawang", "Ziro"],
    "Assam": ["Guwahati", "Dibrugarh", "Silchar", "Tezpur"],
    "Bihar": ["Patna", "Gaya", "Bhagalpur", "Muzaffarpur"],
    "Chhattisgarh": ["Raipur", "Bhilai", "Bilaspur", "Korba"],
    "Goa": ["Panaji", "Margao", "Vasco da Gama"],
    "Gujarat": ["Ahmedabad", "Surat", "Vadodara", "Rajkot"],
    "Haryana": ["Gurgaon", "Faridabad", "Panipat", "Hisar"],
    "Himachal Pradesh": ["Shimla", "Manali", "Dharamshala"],
    "Jharkhand": ["Ranchi", "Jamshedpur", "Dhanbad", "Bokaro"],
    "Karnataka": ["Bengaluru", "Mysuru", "Mangalore", "Hubli"],
    "Kerala": ["Kochi", "Thiruvananthapuram", "Kozhikode"],
    "Madhya Pradesh": ["Bhopal", "Indore", "Gwalior", "Jabalpur"],
    "Maharashtra": ["Mumbai", "Pune", "Nagpur", "Nashik", "Aurangabad"],
    "Manipur": ["Imphal"],
    "Meghalaya": ["Shillong"],
    "Mizoram": ["Aizawl"],
    "Nagaland": ["Kohima", "Dimapur"],
    "Odisha": ["Bhubaneswar", "Cuttack", "Rourkela"],
    "Punjab": ["Ludhiana", "Amritsar", "Jalandhar", "Patiala"],
    "Rajasthan": ["Jaipur", "Jodhpur", "Udaipur", "Kota"],
    "Sikkim": ["Gangtok"],
    "Tamil Nadu": ["Chennai", "Coimbatore", "Madurai", "Salem"],
    "Telangana": ["Hyderabad", "Warangal", "Nizamabad"],
    "Tripura": ["Agartala"],
    "Uttar Pradesh": ["Lucknow", "Noida", "Kanpur", "Varanasi", "Agra"],
    "Uttarakhand": ["Dehradun", "Haridwar", "Nainital"],
    "West Bengal": ["Kolkata", "Siliguri", "Asansol", "Howrah", "Durgapur", "Malda"],
    "Delhi": ["New Delhi", "Dwarka", "Rohini", "South Delhi"],
    "Jammu and Kashmir": ["Srinagar", "Jammu"],
    "Ladakh": ["Leh", "Kargil"],
    "Chandigarh": ["Chandigarh"],
    "Puducherry": ["Puducherry"],
    "Andaman and Nicobar Islands": ["Port Blair"],
    "Dadra and Nagar Haveli and Daman and Diu": ["Daman", "Silvassa"]
}

# ------------------- SERP API --------------------
def get_google_rank(keyword, brand_url, country='in', lang='en', location=None, show_serp=False):
    """Use SerpApi for real-time Google rank"""
    params = {
        "engine": "google",
        "q": keyword,
        "hl": lang,
        "gl": country,
        "num": 100,
        "api_key": SERP_API_KEY
    }

    if location:
        params["location"] = location

    res = requests.get("https://serpapi.com/search", params=params)
    data = res.json()

    if "error" in data:
        st.warning(f"⚠️ SerpAPI Error for '{keyword}': {data['error']}")
        return "API Error", []

    results = data.get("organic_results", [])
    brand_domain = re.sub(r"^https?://(www\.)?", "", brand_url).split("/")[0].lower()

    serp_links = []
    for i, r in enumerate(results, 1):
        link = r.get("link", "").lower()
        serp_links.append({"Position": i, "URL": link})
        if brand_domain in link:
            return i, serp_links

    return "Not Found", serp_links

# ------------------- STREAMLIT UI --------------------
st.set_page_config(page_title="Keyword Rank Tracker", page_icon="🔍", layout="centered")

st.title("🔍 Keyword Rank Tracker (SerpApi Powered)")
st.caption("Real-time Google rank checker with full India → State → City targeting")

# ---- Sidebar ----
st.sidebar.header("⚙️ Location Settings")
country = st.sidebar.selectbox("🌎 Country", ["India", "United States", "United Kingdom", "Canada", "Australia"], index=0)
lang = st.sidebar.selectbox("🗣️ Language", ["en", "hi", "fr", "es", "de"], index=0)

# Dynamic State → City selector
state, city, location = None, None, None
if country == "India":
    state = st.sidebar.selectbox("🏙️ Select State or UT", ["All India"] + sorted(INDIA_STATES_CITIES.keys()))
    if state != "All India":
        cities = INDIA_STATES_CITIES[state]
        city = st.sidebar.selectbox("🏘️ Select City", ["All Cities"] + cities)
        custom_city = st.sidebar.text_input("Or enter custom city (optional)")
        if custom_city.strip():
            city = custom_city.strip().title()

        if city != "All Cities":
            location = f"{city}, {state}, India"
        else:
            location = f"{state}, India"
    else:
        location = "India"
else:
    location = country

show_history = st.sidebar.checkbox("📜 Show Rank History", value=False)
show_serp = st.sidebar.checkbox("🔗 Show SERP URLs (Debug)", value=False)

# ---- Input Form ----
with st.form("rank_form"):
    brand_url = st.text_input("Enter your Brand URL", placeholder="https://digitalpiloto.com")
    keywords_text = st.text_area(
        "Enter Keywords (one per line)",
        placeholder="AI SEO Expert\nDigital Marketing Company in Kolkata\nSEO Agency in India"
    )
    submitted = st.form_submit_button("Check Rankings")

# ---- Rank Checker ----
if submitted:
    if not brand_url or not keywords_text.strip():
        st.error("⚠️ Please enter both Brand URL and Keywords.")
    else:
        st.info(f"🌍 Targeting location: **{location}**")
        keywords = [k.strip() for k in keywords_text.split("\n") if k.strip()]
        results = []
        progress = st.progress(0)
        status = st.empty()

        for i, kw in enumerate(keywords):
            status.text(f"🔍 Checking: {kw} ...")
            rank, serp_links = get_google_rank(kw, brand_url, "in", lang, location, show_serp)
            save_rank(brand_url, kw, rank, "in", lang, location)

            results.append({
                "Keyword": kw,
                "Rank": rank,
                "Location": location,
                "Checked At": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            progress.progress((i + 1) / len(keywords))
            time.sleep(1)

            if show_serp and serp_links:
                with st.expander(f"🔗 SERP Links for '{kw}'"):
                    df_serp = pd.DataFrame(serp_links)
                    st.dataframe(df_serp, use_container_width=True)

        st.success("✅ Rank check completed successfully!")

        df_results = pd.DataFrame(results)
        st.dataframe(df_results, use_container_width=True)

        csv = df_results.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Results as CSV",
            data=csv,
            file_name="keyword_ranks.csv",
            mime="text/csv"
        )

# ---- Rank History ----
if show_history:
    st.subheader("📜 Rank History")
    hist = get_history()
    if not hist.empty:
        st.dataframe(hist, use_container_width=True)
        csv = hist.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download History", csv, "rank_history.csv", "text/csv")
    else:
        st.info("No history found yet — run a rank check to start building data.")

# ---- Footer ----
st.markdown("---")
st.caption("Digital Piloto Rank Tracker | © 2025 Digital Piloto AI")
