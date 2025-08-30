import os
import requests
from bs4 import BeautifulSoup
import feedparser
from dotenv import load_dotenv
from datetime import datetime
import time
from email_utils import send_email

# Force it to load from current dir
from pathlib import Path

# Only load .env if it exists (local dev)
env_path = Path(".") / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)

HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN")
MODEL_ID = os.getenv("MODEL_ID", "facebook/bart-large-cnn")
MAX_ARTICLES_PER_FEED = int(os.getenv("MAX_ARTICLES_PER_FEED", 5))  # default 5

HEADERS = {"Authorization": f"Bearer {HUGGINGFACE_TOKEN}"}


def summarize_text(text):
    #Summarize text using HuggingFace API
    API_URL = f"https://api-inference.huggingface.co/models/{MODEL_ID}"
    response = requests.post(API_URL, headers=HEADERS, json={"inputs": text[:3000]})
    if response.status_code == 200:
        return response.json()[0]['summary_text']
    else:
        return f"[Error {response.status_code}] {response.text}"


def clean_investing_article(url):
    # Scrape and clean Investing.com article (remove nav, ads, boilerplate)
    res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    if res.status_code != 200:
        return f"[Error] {url} returned {res.status_code}"

    soup = BeautifulSoup(res.text, "html.parser")

    # Investing.com content usually lives inside <div class="WYSIWYG articlePage"> or <div class="article">
    article_div = soup.find("div", {"class": ["WYSIWYG", "articlePage", "article"]})
    if not article_div:
        # fallback: just grab paragraphs
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    else:
        paragraphs = [p.get_text(" ", strip=True) for p in article_div.find_all("p")]

    # Remove junk (very short paragraphs, common boilerplate)
    cleaned = [p for p in paragraphs if len(p.split()) > 5 and "Investing.com" not in p]

    return " ".join(cleaned)


def scrape_investing_rss(feed_url, max_articles=5):
    #Parse investing.com RSS feed and summarize articles
    feed = feedparser.parse(feed_url)
    summaries = []

    for entry in feed.entries[:max_articles]:
        title = entry.title
        link = entry.link
        print(f"Fetching: {title} ({link})")

        text = clean_investing_article(link)
        if not text or len(text.split()) < 50:
            print(f"[WARN] Skipping {link}, too little text")
            continue

        summary = summarize_text(text)
        summaries.append(f"# {title}\n\n{summary}\n\n🔗 {link}")

    return summaries


def main():
    # Load Investing.com RSS URLs from text file
    urls_file = "investing_urls.txt"
    if not os.path.exists(urls_file):
        print(f"[ERROR] File {urls_file} does not exist!")
        return

    with open(urls_file, "r", encoding="utf-8-sig") as f:
        urls = [line.strip() for line in f if line.strip()]

    all_summaries = []

    # Loop through all URLs
    for url in urls:
        print(f"Processing {url}")
        summaries = scrape_investing_rss(url)
        all_summaries.extend(summaries)

    # Save results
    out_file = f"outputs/investing_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    os.makedirs("ng-outputs", exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("\n\n---\n\n".join(all_summaries))

    print(f"\n✅ Investing.com summaries saved to {out_file}")

    # === EMAIL DIGEST ===
    subject = "Daily NG News"

    # Wrap in HTML list
    html_body = "<h2>Daily NG News Digest</h2><ol>"
    for summary in all_summaries:
        html_body += f"<li>{summary}</li><br>"
    html_body += "</ol>"

    recipient = os.getenv("EMAIL_RECIPIENT")  # REAL EMAIL
    print(f"\n📧 Sending email digest to {recipient} ...")
    send_email(subject, html_body, recipient, is_html=True)


if __name__ == "__main__":
    main()
