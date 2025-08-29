import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from datetime import datetime
import feedparser
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
from scraper_bloomberg import scrape_bloomberg
from email_utils import send_email

# Force it to load from current dir
from pathlib import Path

# Only load .env if it exists (local dev)
env_path = Path(".") / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)
    
HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN")
print(HUGGINGFACE_TOKEN)
MODEL_ID = os.getenv("MODEL_ID", "facebook/bart-large-cnn") #("MODEL_ID")#, "facebook/bart-large-cnn")
print(MODEL_ID)
MAX_ARTICLES_PER_FEED = int(os.getenv("MAX_ARTICLES_PER_FEED", 5))  # default 5
#TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
#TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

HEADERS = {"Authorization": f"Bearer {HUGGINGFACE_TOKEN}"}

def scrape_url(url, scraper_hint=None):
    #Scrape content from URL using RSS, Requests+Soup, or Selenium
    if scraper_hint:
        print(f"[SCRAPER] Using {scraper_hint} for {url}")
        
    # 1. Try RSS feed first
    if url.endswith(".rss") or "rss" in url:
        print(f"[SCRAPER] Using feedparser RSS for {url}")
        feed = feedparser.parse(url)
        if feed.entries:
            content = []
            for entry in feed.entries[:MAX_ARTICLES_PER_FEED]:
                title = entry.title
                summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
                link = entry.link
                content.append(f"{title}\n{summary}\n{link}")
            return "\n\n".join(content)  # <- RETURN here, don’t continue

    # 2. Try normal requests for non-RSS pages
    try:
        res = requests.get(url, timeout=15, 
        headers={"User-Agent": "Mozilla/5.0"
            "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/117.0.0.0 Safari/537.36"
        })
        print(f"[SCRAPER] Using requests + BeautifulSoup for {url}")
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            for tag in ["article", "main", "div", "p"]:
                content = " ".join([el.get_text(" ", strip=True) for el in soup.find_all(tag)])
                if len(content.split()) > 50:
                    return content
            return soup.get_text()
        else:
            return f"[Requests Error] Status code: {res.status_code}"
    except Exception as e:
        print(f"[Requests Error] {e}")

    # 3. Selenium fallback for JS-heavy pages
    try:
        print(f"[SCRAPER] Using Selenium for {url}")
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=options)
        driver.get(url)
        time.sleep(5)
        html = driver.page_source
        driver.quit()

        soup = BeautifulSoup(html, "html.parser")
        content = " ".join([el.get_text(" ", strip=True) for el in soup.find_all("p")])
        return content if content else soup.get_text()
    except Exception as e:
        return f"[Selenium Error] {e}"

def summarize_text(text):
    #Summarize text using HuggingFace Inference API
    API_URL = f"https://api-inference.huggingface.co/models/{MODEL_ID}"
    response = requests.post(API_URL, headers=HEADERS, json={"inputs": text[:3000]})
    if response.status_code == 200:
        return response.json()[0]['summary_text']
    else:
        return f"[Error {response.status_code}] {response.text}"

#def send_telegram(message):
    #if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        #return
    #url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    #requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message})

# def fetch_daily_urls():
#     sources = [
#         "https://finance.yahoo.com/rss/headline?s=AAPL",
#         "https://finance.yahoo.com/rss/headline?s=TSLA",
#         "https://www.nasdaq.com/feed/rssoutbound",
#         "https://www.prnewswire.com/rss/all-news-releases-list.rss"
#     ]
#     urls = []
#     for src in sources:
#         feed = feedparser.parse(src)
#         for entry in feed.entries[:5]:  # top 5 per source
#             urls.append(entry.link)
#     return urls

def scrape_rss(url):
    #Extract article links from RSS feed and return their contents
    feed = feedparser.parse(url)
    articles = []
    for entry in feed.entries[:5]:  # take top 5 from feed
        link = entry.link
        print(f"Fetching article: {link}")
        text = scrape_url(link)  # reuse scrape_url for each article
        if text:
            articles.append((link, text))
    return articles    
    
def main():
    os.makedirs("outputs", exist_ok=True)
    with open("urls.txt", encoding="utf-8-sig") as f:
        urls = [u.strip() for u in f if u.strip()]

    all_summaries = []

    for url in urls:
        print(f"Processing {url}")

        # --- Bloomberg special handling ---
        if "bloomberg.com" in url:
            print(f"[SCRAPER] Bloomberg article detected → {url}")
            results = scrape_bloomberg(url)  # now always returns a list
            for title, text in results:
                if not text.strip():
                    print(f"[WARN] Empty text for {title}")
                    continue
                summary = summarize_text(text)
                formatted = f"# {title}\n\n{summary}\n\n🔗 {url}"
                all_summaries.append(formatted)

        # --- RSS Feeds (non-Bloomberg) ---
        elif url.endswith(".rss") or "rss" in url.lower():
            print(f"[SCRAPER] Identified as RSS feed → {url}")
            articles = scrape_rss(url)
            for link, text in articles:
                if not text.strip():
                    print(f"[WARN] Empty text for {link}")
                    continue
                summary = summarize_text(text)
                formatted = f"# Summary of {link}\n\n{summary}"
                all_summaries.append(formatted)

        # --- Generic web pages ---
        else:
            print(f"[SCRAPER] Identified as direct page → {url}")
            text = scrape_url(url)
            if not text.strip():
                print(f"[WARN] Empty text for {url}")
                continue
            summary = summarize_text(text)
            formatted = f"# Summary of {url}\n\n{summary}"
            all_summaries.append(formatted)

    # Save everything into ONE combined file
    out_file = f"outputs/combined_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("\n\n---\n\n".join(all_summaries))

    print(f"\n✅ All summaries saved to: {out_file}")

    # === EMAIL DIGEST ===
    subject = "Your Daily News Digest"

    # Wrap in HTML list
    html_body = "<h2>Daily News Digest</h2><ol>"
    for summary in all_summaries:
        html_body += f"<li>{summary}</li><br>"
    html_body += "</ol>"

    recipient = os.getenv("EMAIL_RECIPIENT")  # REAL EMAIL
    print(f"\n📧 Sending email digest to {recipient} ...")
    send_email(subject, html_body, recipient, is_html=True)

if __name__ == "__main__":
    main()
