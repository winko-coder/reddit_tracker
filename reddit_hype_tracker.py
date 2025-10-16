!pip install requests textblob pandas python-telegram-bot --quiet
!pip install praw textblob pandas python-telegram-bot --quiet

import praw, re, pandas as pd, time
from textblob import TextBlob
from telegram import Bot

import requests
import os

from google.colab import drive
drive.mount('/content/drive')
HISTORY_FILE = "/content/drive/MyDrive/reddit_trends.csv"

# === Reddit API ===
reddit = praw.Reddit(
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_USER_AGENT
)

# === Telegram-Konfiguration ===
BOT_TOKEN = "8373278064:AAHNvQRzo7t_jvakcUFxn-_UcHlQxpfUw5c"
CHAT_ID = 8226887753
bot = Bot(token=BOT_TOKEN)

# === Parameter ===
SUBREDDITS = ["wallstreetbets", "stocks", "investing"]
POST_LIMIT = 300
TOP_N = 10             # Anzahl der meistgenannten Ticker pro Zyklus
CYCLE_DELAY = 3600     # Pause zwischen Zyklen (in Sekunden)


# === Funktionen ===
def get_tickers():
    """Sammelt Ticker aus den angegebenen Subreddits."""
    data = []
    for sub in SUBREDDITS:
        for comment in reddit.subreddit(sub).comments(limit=POST_LIMIT):
            text = comment.body
            found = re.findall(r"\b[A-Z]{2,5}\b", text)
            for t in found:
                if t not in ["USD","CEO","ETF","AI","USA","GDP","EPS","IPO"]:
                    sentiment = TextBlob(text).sentiment.polarity
                    data.append((t, sentiment))
    return pd.DataFrame(data, columns=["ticker","sentiment"])

def summarize(df):
    """Fasst Erwähnungen und Sentiment je Ticker zusammen."""
    if df.empty:
        return pd.DataFrame(columns=["ticker","mentions","sentiment"])
    grouped = df.groupby("ticker").agg(
        mentions=("ticker","count"),
        sentiment=("sentiment","mean")
    ).reset_index().sort_values(by="mentions", ascending=False)
    return grouped

def get_price(ticker):
    """Holt aktuellen Kurs (optional, Fehler robust)."""
    try:
        data = yf.download(ticker, period="1d", interval="1m", progress=False)
        return round(data["Close"].iloc[-1], 2)
    except:
        return None

def send_update(top_df):
    """Sendet Telegram-Nachricht mit Top-Tickern (synchron, kein await nötig)."""
    msg = "📈 *Reddit Trending Stocks*\n\n"
    for _, row in top_df.iterrows():
        msg += f"{row['ticker']}: {row['mentions']} Erwähnungen, Sentiment {row['sentiment']:.2f}\n"
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    requests.post(url, data=data)

def load_history():
    """Lädt bisherigen Trendverlauf (falls vorhanden)."""
    if os.path.exists(HISTORY_FILE):
        return pd.read_csv(HISTORY_FILE)
    else:
        return pd.DataFrame(columns=["timestamp", "ticker", "mentions"])

def save_cycle(df):
    """Speichert aktuelle Erwähnungen mit Zeitstempel."""
    ts = pd.Timestamp.now()
    df = df[["ticker", "mentions"]].copy()
    df["timestamp"] = ts
    df.to_csv(HISTORY_FILE, mode="a", header=not os.path.exists(HISTORY_FILE), index=False)

def compute_trends():
    """Analysiert Trends über die Zeit."""
    hist = load_history()
    if hist.empty:
        return pd.DataFrame()
    trend = hist.groupby(["ticker"]).agg(
        avg_mentions=("mentions", "mean"),
        last_mentions=("mentions", "last"),
        count=("mentions", "count")
    ).reset_index()
    trend["trend_strength"] = (trend["last_mentions"] - trend["avg_mentions"]) / (trend["avg_mentions"] + 1)
    trend = trend.sort_values("trend_strength", ascending=False)
    return trend

def send_telegram(msg):
  url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
  data = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
  requests.post(url, data=data)

# === Hauptloop ===
print("🚀 Reddit-Hype-Tracker gestartet.")
for cycle in range(3):  # z. B. 3 Stunden Laufzeit
    print(f"\n⏳ Zyklus {cycle+1} ...")
    df = get_tickers()
    summary = summarize(df)
    top = summary.head(TOP_N)

    save_cycle(top)
    trend_df = compute_trends().head(5)

    print(top)
    send_update(top)
    print(f"✅ Zyklus {cycle+1} abgeschlossen – nächste Abfrage in {CYCLE_DELAY/60:.0f} min.")

    msg = "📈 *Reddit Trending Stocks*\n\n"
    for _, row in top.iterrows():
        msg += f"{row['ticker']}: {row['mentions']} Erwähnungen, Sentiment {row['sentiment']:.2f}\n"
    msg += "\n🔥 *Langfristige Trends:*\n"
    for _, row in trend_df.iterrows():
        msg += f"{row['ticker']}: Trend {row['trend_strength']:+.2f}\n"

    send_telegram(msg)
    print("\n")
    print(msg)

    time.sleep(CYCLE_DELAY)
