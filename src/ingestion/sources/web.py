# src/ingestion/sources/web.py
import urllib.request
from bs4 import BeautifulSoup


def ingest(source, since):
    with urllib.request.urlopen(source["url"]) as response:
        html = response.read()
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for article in soup.find_all("article"):
        title_tag = article.find(["h1", "h2", "h3"])
        title = title_tag.get_text(strip=True) if title_tag else ""
        p_tag = article.find("p")
        summary = p_tag.get_text(strip=True) if p_tag else ""
        items.append({
            "title": title,
            "url": source["url"],
            "summary": summary,
            "source_id": source["id"],
        })
    return items
