import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
import warnings

# Suppress BeautifulSoup warning when parsing XML as HTML
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


def scrape_bloomberg(url, limit=5):
    """
    Scraper for Bloomberg articles and RSS feeds.
    Returns list of (title, body_text).
    """

    print(f"[Bloomberg] Scraping {url}")

    def extract_title(soup):
        # Title candidates
        selectors = [
            "h1.article-headline",
            "h1[data-component='headline']",
            "h1",
            "title",
        ]
        for sel in selectors:
            el = soup.select_one(sel)
            if el:
                return el.get_text(" ", strip=True)
        return "Untitled Article"

    def extract_body(soup):
        selectors = [
            "div.body-content",
            "section.article-body__content",
            "div.article-body__content",
            "div.body-copy",
            "div.article__content",
        ]
        for sel in selectors:
            container = soup.select_one(sel)
            if container:
                paragraphs = container.find_all(["p", "span"])
                text = " ".join([p.get_text(" ", strip=True) for p in paragraphs])
                if len(text.split()) > 50:
                    return text
        # fallback: all <p>
        paragraphs = soup.find_all("p")
        return " ".join([p.get_text(' ', strip=True) for p in paragraphs])

    # --- Detect if RSS feed ---
    if url.endswith(".xml") or "rss" in url.lower():
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            soup = BeautifulSoup(r.text, "xml")
            items = soup.find_all("item")

            links = []
            for item in items:
                link = item.find("link")
                if link:
                    links.append(link.get_text(strip=True))

            print(f"[Bloomberg RSS] Found {len(links)} articles")
            results = []
            seen = set()
            for link in links:
                if link in seen:
                    continue
                seen.add(link)

                article_data = scrape_bloomberg(link)  # recursive call
                if isinstance(article_data, list):
                    results.extend(article_data)
                else:
                    results.append(article_data)

                if len(results) >= limit:
                    break
            return results
        except Exception as e:
            print(f"[Bloomberg RSS Error] {e}")
            return [("Bloomberg RSS Error", str(e))]

    # --- Article scraper ---
    try:
        res = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            title = extract_title(soup)
            body = extract_body(soup)
            return [(title, body)]
    except Exception as e:
        print(f"[Bloomberg Requests Error] {e}")

    # --- Fallback: Selenium ---
    try:
        print(f"[Bloomberg] Using Selenium for {url}")
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
        title = extract_title(soup)
        body = extract_body(soup)
        return [(title, body)]
    except Exception as e:
        return [("Bloomberg Error", f"[Bloomberg Selenium Error] {e}")]
