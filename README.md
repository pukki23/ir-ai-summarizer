# IR AI Summarizer (MVP)

### What it does
- Scrapes press releases / filings from URLs in `urls.txt`
- Summarizes text with Hugging Face Inference API
- Saves results in `outputs/`
- (Optional) Sends to Telegram bot

### Setup
1. Clone repo and install deps:
   python -m venv .venv
   source .venv/bin/activate   # or .venv\Scripts\activate on Windows
   pip install -r requirements.txt

2. Copy .env.example → .env and set Hugging Face + Telegram tokens.

3. Add URLs to `urls.txt`.

4. Run:
   python scrape_and_summarize.py
