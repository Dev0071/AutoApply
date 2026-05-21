import httpx
import structlog
from bs4 import BeautifulSoup

log = structlog.get_logger()


class JDMiner:
    def __init__(self, timeout: int = 15):
        self._timeout = timeout

    async def fetch(self, url: str) -> dict:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(url)
            response.raise_for_status()

        text = self._extract_text(response.text)
        keywords = self._extract_keywords(text)

        log.info("jd_fetched", url=url, keyword_count=len(keywords))
        return {"url": url, "raw_jd_text": text, "keywords": keywords}

    def _extract_text(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        return soup.get_text(separator=" ", strip=True)

    def _extract_keywords(self, text: str) -> list[str]:
        common_tech = {
            "python", "typescript", "javascript", "react", "fastapi", "postgresql",
            "redis", "docker", "kubernetes", "aws", "gcp", "sql", "rest", "graphql",
        }
        words = {w.lower().strip(".,") for w in text.split()}
        return sorted(words & common_tech)
