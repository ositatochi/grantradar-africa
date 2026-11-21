import os
import time
from math import ceil
from urllib.parse import urlparse

from django.core.cache import cache
from scrapy import Request, Spider

BOT_NAME = "grantradar"
SPIDER_MODULES = ["apps.crawler.spiders"]
NEWSPIDER_MODULE = "apps.crawler.spiders"
ROBOTSTXT_OBEY = True
USER_AGENT = os.environ.get(
    "CRAWLER_USER_AGENT",
    "GrantRadarAfricaBot/0.1 (+https://ositatochi.com.ng)",
)
DOWNLOAD_DELAY = 1.0
CONCURRENT_REQUESTS_PER_DOMAIN = 1
DOWNLOAD_TIMEOUT = 20
RETRY_TIMES = 3
ITEM_PIPELINES = {"apps.crawler.pipelines.RawDocumentPipeline": 300}
DOWNLOADER_MIDDLEWARES = {
    "apps.crawler.spiders.PublicNetworkGuardMiddleware": 50,
    "apps.crawler.scrapy_settings.DomainRateLimitMiddleware": 60,
}
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}
PLAYWRIGHT_BROWSER_TYPE = "chromium"


class DomainRateLimitMiddleware:
    def process_request(self, request: Request, spider: Spider) -> None:
        retry_delay = min(2 ** request.meta.get("retry_times", 0), 60)
        if retry_delay > 1:
            time.sleep(retry_delay - 1)
        host = urlparse(request.url).hostname or "unknown"
        delay = max(1, ceil(float(os.environ.get("CRAWLER_DOMAIN_MIN_DELAY_SECONDS", "1"))))
        while not cache.add(f"crawler-domain:{host}", "1", timeout=delay):
            time.sleep(0.1)
