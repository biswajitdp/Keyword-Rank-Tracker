import os
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
    conn.close()

def save_rank(brand_url, keyword, rank, country, lang):
    conn = sqlite3.connect(DB)
    conn.execute(
        "INSERT INTO ranks (brand_url, keyword, rank, country, lang) VALUES (?, ?, ?, ?, ?)",
        (brand_url, keyword, str(rank), country, lang)
    )
    conn.commit()
    conn.close()

def get_history():
    conn = sqlite3.connect(DB)
    df = pd.read_sql_query("SELECT * FROM ranks ORDER BY checked_at DESC", conn)
    conn.close()
    return df

init_db()

# ------------------- SERP API --------------------
def get_google_rank(keyword, brand_url, country='in', lang='en'):
    """Use SerpApi for real-time Google rank"""
    params = {
        "engine": "google",
        "q": keyword,
        "hl": lang,
        "gl": country,
        "num": 100,
        "api_key": SERP_API_KEY
    }

    res = requests.get("https://serpapi.com/search", params=params)
    data = res.json()

    if "error" in data:
        st.warning(f"⚠️ SerpAPI Error for '{keyword}': {data['error']}")
        return "API Error"

    results = data.get("organic_results", [])
    brand_domain = brand_url.replace("https://", "").replace("http://", "").split("/")[0]

    for i, r in enumerate(results, 1):
        if brand_domain in r.get("link", ""):
            return i
    return "Not Found"

# ------------------- STREAMLIT UI --------------------
st.set_page_config(page_title="Keyword Rank Tracker", page_icon="🔍", layout="centered")

st.title("🔍 Keyword Rank Tracker")
st.caption("Real-time keyword rank checker using live Google data")

st.sidebar.header("⚙️ Settings")
country = st.sidebar.selectbox("🌎 Country", ["in", "us", "uk", "ca", "au"], index=0)
lang = st.sidebar.selectbox("🗣️ Language", ["en", "hi", "fr", "es", "de"], index=0)
show_history = st.sidebar.checkbox("Show Rank History", value=False)

# ---- Input Form ----
with st.form("rank_form"):
    brand_url = st.text_input("Enter your Brand URL", placeholder="https://www.example.com")
    keywords_text = st.text_area(
        "Enter Keywords (one per line)",
        placeholder="AI SEO Expert\nDigital Marketing Company in Kolkata\nSEO Agency in India"
    )
    submitted = st.form_submit_button("Check Rankings")

if submitted:
    if not brand_url or not keywords_text.strip():
        st.error("⚠️ Please enter both Brand URL and Keywords.")
    else:
        keywords = [k.strip() for k in keywords_text.split("\n") if k.strip()]
        results = []
        progress = st.progress(0)
        status = st.empty()

        for i, kw in enumerate(keywords):
            status.text(f"Checking: {kw} ...")
            rank = get_google_rank(kw, brand_url, country, lang)
            save_rank(brand_url, kw, rank, country, lang)
            results.append({
                "Keyword": kw,
                "Rank": rank,
                "Checked At": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            progress.progress((i + 1) / len(keywords))
            time.sleep(1)

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

# ---- History ----
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
st.caption("Digital Piloto Rank tracker | © 2025 Digital Piloto AI")
