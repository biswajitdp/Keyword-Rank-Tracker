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
            location TEXT,
            checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    for coldef in [("page", "TEXT"), ("ranked_url", "TEXT")]:
        try:
            conn.execute(f"ALTER TABLE ranks ADD COLUMN {coldef[0]} {coldef[1]}")
        except sqlite3.OperationalError:
            pass
    conn.close()

def save_rank(brand_url, keyword, rank, page, ranked_url, country, lang, location):
    conn = sqlite3.connect(DB)
    conn.execute(
        "INSERT INTO ranks (brand_url, keyword, rank, page, ranked_url, country, lang, location) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (brand_url, keyword, str(rank), str(page), ranked_url, country, lang, location),
    )
    conn.commit()
    conn.close()

def get_history():
    conn = sqlite3.connect(DB)
    df = pd.read_sql_query("SELECT * FROM ranks ORDER BY checked_at DESC", conn)
    conn.close()
    return df

init_db()

# ------------------- STATE LIST --------------------
INDIA_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa",
    "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala",
    "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland",
    "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
    "Uttar Pradesh", "Uttarakhand", "West Bengal", "Delhi", "Jammu and Kashmir",
    "Ladakh", "Chandigarh", "Puducherry", "Andaman and Nicobar Islands",
    "Dadra and Nagar Haveli and Daman and Diu"
]

# ------------------- SERP API --------------------
def get_google_rank(keyword, brand_url, country="in", lang="en", location=None, show_serp=False):
    """Fetch rank from top 100 Google results using SerpApi pagination"""
    brand_domain = re.sub(r"^https?://(www\.)?", "", brand_url).split("/")[0].lower()

    serp_links = []
    found_rank, found_page, found_url = None, None, None

    for page_num, start in enumerate(range(0, 100, 10), start=1):
        params = {
            "engine": "google",
            "q": keyword,
            "hl": lang,
            "gl": country,
            "num": 10,
            "start": start,
            "api_key": SERP_API_KEY,
        }
        if location:
            params["location"] = location

        try:
            res = requests.get("https://serpapi.com/search", params=params, timeout=15)
            data = res.json()
        except Exception as e:
            st.warning(f"⚠️ Network error: {e}")
            return "API Error", "-", "-", []

        if "error" in data:
            st.warning(f"⚠️ SerpApi Error for '{keyword}': {data['error']}")
            return "API Error", "-", "-", []

        results = data.get("organic_results", [])
        for i, r in enumerate(results, start + 1):
            link = r.get("link", "").lower()
            serp_links.append({"Position": i, "URL": link})
            if brand_domain in link:
                found_rank, found_page, found_url = i, page_num, link
                break

        if found_rank:
            break
        time.sleep(0.5)

    if found_rank:
        return found_rank, found_page, found_url, serp_links
    return "Not Found", "-", "-", serp_links

# ------------------- STREAMLIT UI --------------------
st.set_page_config(page_title="Keyword Rank Tracker", page_icon="🔍", layout="centered")

st.title("🔍 Keyword Rank Tracker")
st.caption("Real-time Google Rank Tracker with Country → State → City selection (optional)")

# ---- Sidebar ----
st.sidebar.header("⚙️ Location Settings")

country = st.sidebar.selectbox(
    "🌎 Country",
    ["India", "United States", "United Kingdom", "Canada", "Australia"],
    index=0
)
lang = st.sidebar.selectbox("🗣️ Language", ["en", "hi", "fr", "es", "de"], index=0)

# ✅ Add State & City selectors (optional)
state = None
city = None
if country == "India":
    state = st.sidebar.selectbox("🏙️ State (optional)", ["-- None --"] + INDIA_STATES)
    city = st.sidebar.text_input("🏘️ City (optional)", "", help="Leave blank if not targeting specific city")

# build final location logic
if country != "India":
    location = country
else:
    if state and state != "-- None --":
        if city.strip():
            location = f"{city.strip().title()}, {state}, India"
        else:
            location = f"{state}, India"
    else:
        location = "India"

show_history = st.sidebar.checkbox("📜 Show Rank History", value=False)
show_serp = st.sidebar.checkbox("🔗 Show SERP URLs (Debug)", value=False)

# Optional DB reset button
if st.sidebar.button("🧹 Reset Database"):
    if os.path.exists(DB):
        os.remove(DB)
        init_db()
        st.sidebar.success("Database reset successfully!")

# ---- Input Form ----
with st.form("rank_form"):
    brand_url = st.text_input("Enter your Brand URL", placeholder="https://www.example.com")
    keywords_text = st.text_area(
        "Enter Keywords (one per line)",
        placeholder="3 bhk flat interior design cost in kolkata\ninterior designer in kolkata",
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
            status.text(f"🔍 Checking: {kw} (Top 100)…")
            rank, page, ranked_url, serp_links = get_google_rank(kw, brand_url, "in", lang, location, show_serp)
            save_rank(brand_url, kw, rank, page, ranked_url, "in", lang, location)

            results.append({
                "Keyword": kw,
                "Rank": rank,
                "Page": page,
                "Ranked URL": ranked_url if ranked_url != "-" else "Not Found",
                "Location": location,
                "Checked At": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })
            progress.progress((i + 1) / len(keywords))
            time.sleep(1)

            if show_serp and serp_links:
                with st.expander(f"🔗 SERP Links for '{kw}'"):
                    st.dataframe(pd.DataFrame(serp_links), use_container_width=True)

        st.success("✅ Rank check completed successfully!")
        df_results = pd.DataFrame(results)
        st.dataframe(df_results, use_container_width=True)

        csv = df_results.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download Results as CSV", csv, "keyword_ranks.csv", "text/csv")

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

st.markdown("---")
st.caption("Digital Piloto Rank Tracker | © 2025 Digital Piloto AI")
