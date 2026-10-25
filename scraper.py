import requests
import csv
import time
import logging
from pathlib import Path
from collections import Counter
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Project paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
REPORT_DIR = BASE_DIR / "reports"
LOG_DIR = BASE_DIR / "logs"

DATA_DIR.mkdir(exist_ok=True)
REPORT_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

CSV_FILE = DATA_DIR / "news.csv"
REPORT_FILE = REPORT_DIR / "summary_report.txt"
LOG_FILE = LOG_DIR / "scraper.log"

URL = "https://news.ycombinator.com/"

# Logging configuration
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)

# Custom headers
HEADERS = {
    "User-Agent": "EducationalNewsScraper/1.0",
    "Accept": "text/html"
}


def create_session():
    """Create a session with retry configuration."""
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        respect_retry_after_header=True
    )

    adapter = HTTPAdapter(max_retries=retry_strategy)

    session = requests.Session()
    session.headers.update(HEADERS)
    session.mount("https://", adapter)

    return session


def fetch_html(session):
    """Fetch website HTML with rate limiting and timeout."""
    time.sleep(2)

    response = session.get(URL, timeout=15)
    response.raise_for_status()

    logging.info("Website fetched successfully")

    return response.text


def extract_news(html):
    """Extract news title, URL, score and author."""
    soup = BeautifulSoup(html, "html.parser")

    news_rows = soup.select("tr.athing")
    records = []
    seen_urls = set()

    for news in news_rows:
        title_tag = news.select_one("span.titleline > a")

        if title_tag is None:
            continue

        title = title_tag.get_text(strip=True)
        link = title_tag.get("href", "")

        if not title or not link:
            continue

        # Remove duplicate URLs
        if link in seen_urls:
            continue

        seen_urls.add(link)

        subtext = news.find_next_sibling("tr")

        score_tag = (
            subtext.select_one(".score")
            if subtext else None
        )

        author_tag = (
            subtext.select_one(".hnuser")
            if subtext else None
        )

        score_text = (
            score_tag.get_text(strip=True)
            if score_tag else ""
        )

        # Convert "123 points" to integer 123
        score = None

        if score_text:
            try:
                score = int(score_text.split()[0])
            except (ValueError, IndexError):
                score = None

        author = (
            author_tag.get_text(strip=True)
            if author_tag else ""
        )

        records.append({
            "title": title,
            "url": link,
            "score": score,
            "author": author
        })

    logging.info("Extracted %d unique news records", len(records))

    return records


def save_csv(records):
    """Save extracted data to CSV."""
    fieldnames = ["title", "url", "score", "author"]

    with CSV_FILE.open(
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()
        writer.writerows(records)

    logging.info("CSV saved successfully: %s", CSV_FILE)


def generate_report(records):
    """Generate summary statistics."""
    total_records = len(records)

    missing_titles = sum(
        not record["title"]
        for record in records
    )

    missing_urls = sum(
        not record["url"]
        for record in records
    )

    scores = [
        record["score"]
        for record in records
        if record["score"] is not None
    ]

    average_score = (
        sum(scores) / len(scores)
        if scores else 0
    )

    highest_score = max(scores) if scores else 0

    authors = Counter(
        record["author"]
        for record in records
        if record["author"]
    )

    report = [
        "AUTOMATED WEB SCRAPING REPORT",
        "=" * 35,
        f"Source: {URL}",
        f"Total news records: {total_records}",
        f"Missing titles: {missing_titles}",
        f"Missing URLs: {missing_urls}",
        f"Records with scores: {len(scores)}",
        f"Average score: {average_score:.2f}",
        f"Highest score: {highest_score}",
        "",
        "Top authors:"
    ]

    for author, count in authors.most_common(5):
        report.append(f"{author}: {count} articles")

    REPORT_FILE.write_text(
        "\n".join(report) + "\n",
        encoding="utf-8"
    )

    logging.info("Summary report generated successfully")


def main():
    logging.info("Scraper started")

    session = create_session()

    try:
        html = fetch_html(session)
        records = extract_news(html)

        save_csv(records)
        generate_report(records)

        print("Scraping completed successfully!")
        print("Total news records:", len(records))
        print("CSV file:", CSV_FILE)
        print("Report file:", REPORT_FILE)
        print("Log file:", LOG_FILE)

    except requests.RequestException:
        logging.exception("Website request failed")
        print("Request failed. Check your internet connection.")

    except Exception:
        logging.exception("Unexpected error occurred")
        print("An unexpected error occurred. Check the log file.")

    finally:
        session.close()


if __name__ == "__main__":
    main()