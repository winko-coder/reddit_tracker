import praw
import pandas as pd
import yfinance as yf
from textblob import TextBlob
from datetime import datetime
from collections import Counter
import os
import requests

# === Reddit API Setup ===
reddit = praw.Reddit(
    client_id=os.getenv("CLIENT_ID"),
    client_secret=os.getenv("CLIENT_SECRET"),
    user_agent=os.getenv("USER_AGENT")
)

# === Telegram Setup ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# === Analyse-Parameter ===
SUBREDDITS = ["wallstreetbets", "stocks", "investing"]
LIMIT = 200
TOP_N = 10
CSV_FILE = "reddit_trends.csv"

# === Hilfsfunktionen ===
def extract_tickers(text):
    import re
    return re.findall(r"\b[A-Z]{2,5}\b", text)

def sentiment_score(text):
    return TextBlob(text).sentiment.polarity

def send_telegram_message(text):
    """Schickt Nachricht über Telegram-Bot."""
    if BOT_TOKEN and CHAT_ID:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"⚠️ Telegram-Fehler: {e}")

# === Datensammlung von Reddit ===
all_tickers = []
ticker_sentiments = {}

for sub in SUBREDDITS:
    for post in reddit.subreddit(sub).hot(limit=LIMIT):
        tickers = extract_tickers(post.title + " " + post.selftext)
        score = sentiment_score(post.title + " " + post.selftext)
        for t in tickers:
            all_tickers.append(t)
            ticker_sentiments.setdefault(t, []).append(score)

# === Aggregation ===
counts = Counter(all_tickers)
top_tickers = counts.most_common(TOP_N)

# === Kursdaten abrufen ===
data = []
for ticker, mentions in top_tickers:
    avg_sent = round(sum(ticker_sentiments[ticker]) / len(ticker_sentiments[ticker]), 3)
    try:
        current_price = round(yf.Ticker(ticker).history(period="1d")["Close"].iloc[-1], 2)
    except Exception:
        current_price = None

    data.append({
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Ticker": ticker,
        "Mentions": mentions,
        "Sentiment": avg_sent,
        "CurrentPrice": current_price
    })

df_new = pd.DataFrame(data)

# === Alte Daten laden und zusammenführen ===
if os.path.exists(CSV_FILE):
    df_old = pd.read_csv(CSV_FILE)
    df_all = pd.concat([df_old, df_new], ignore_index=True)
    df_all.drop_duplicates(subset=["Timestamp", "Ticker"], inplace=True)
else:
    df_all = df_new

df_all.to_csv(CSV_FILE, index=False)
print(f"✅ CSV aktualisiert ({len(df_new)} neue Einträge).")

# === Telegram-Zusammenfassung ===
top_message = "<b>📊 Aktuelle Reddit-Trends</b>\n\n"
for _, row in df_new.head(5).iterrows():
    line = f"• <b>{row['Ticker']}</b>: {row['Mentions']} Erwähnungen, Sentiment {row['Sentiment']:+.2f}, Kurs {row['CurrentPrice']}\n"
    top_message += line

top_message += f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}"
send_telegram_message(top_message)

print("📨 Telegram-Update gesendet!")
