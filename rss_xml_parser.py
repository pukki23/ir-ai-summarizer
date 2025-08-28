import requests
import xml.etree.ElementTree as ET

class StreamingRSSParser:
    """
    A lightweight streaming RSS XML pull parser.
    Fetches and parses RSS feeds efficiently without loading the entire feed into memory.
    """

    def __init__(self, url, max_items=5, timeout=20):
        self.url = url
        self.max_items = max_items
        self.timeout = timeout

    def fetch(self):
        """Fetch the RSS feed content as a stream."""
        try:
            response = requests.get(self.url, stream=True, timeout=self.timeout)
            response.raise_for_status()
            return response.iter_content(chunk_size=1024)
        except requests.RequestException as e:
            print(f"[RSS ERROR] Failed to fetch {self.url}: {e}")
            return None

    def parse(self):
        """Parse the RSS feed and yield items up to max_items."""
        stream = self.fetch()
        if stream is None:
            return []

        items = []
        buffer = b""
        context = ET.iterparse(self._chunked_stream(stream), events=("end",))

        for event, elem in context:
            if elem.tag.lower().endswith("item"):
                item = {
                    "title": elem.findtext("title"),
                    "link": elem.findtext("link"),
                    "pubDate": elem.findtext("pubDate"),
                    "description": elem.findtext("description")
                }
                items.append(item)
                elem.clear()  # free memory

                if len(items) >= self.max_items:
                    break

        return items

    def _chunked_stream(self, stream):
        """Helper generator to feed XML parser incrementally."""
        for chunk in stream:
            yield chunk