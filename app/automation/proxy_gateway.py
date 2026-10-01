import os
import requests
import logging

logger = logging.getLogger(__name__)


class ScrapingGateway:
    """
    Unified resilience gateway for multi-portal scraping.
    Supports proxy rotation, custom user-agents, and optional scraping APIs (e.g., Qoest API / ScraperAPI).
    """
    def __init__(self, proxy_url: str = None, scraping_api_key: str = None):
        self.proxy_url = proxy_url or os.getenv("SCRAPING_PROXY_URL", "")
        self.api_key = scraping_api_key or os.getenv("QOEST_API_KEY", os.getenv("SCRAPER_API_KEY", ""))

    def fetch_page(self, url: str, headers: dict = None, render_js: bool = False, timeout: int = 15) -> str:
        headers = headers or {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        # 1. Scraping API option (e.g. Qoest / ScraperAPI with JS rendering)
        if self.api_key:
            try:
                # Standard proxy API endpoint pattern
                api_endpoint = f"https://api.qoest.com/v1/scrape?api_key={self.api_key}&url={url}&render_js={str(render_js).lower()}"
                res = requests.get(api_endpoint, timeout=timeout)
                if res.status_code == 200:
                    return res.text
            except Exception as e:
                logger.warning(f"Scraping API fetch failed, falling back to proxy/direct: {e}")

        # 2. Proxy rotation option
        proxies = None
        if self.proxy_url:
            proxies = {"http": self.proxy_url, "https": self.proxy_url}

        # 3. Direct request with custom headers
        try:
            res = requests.get(url, headers=headers, proxies=proxies, timeout=timeout)
            if res.status_code == 200:
                return res.text
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")

        return ""
