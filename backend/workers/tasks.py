from celery import Celery

from backend.config import settings

celery_app = Celery("autoapply", broker=settings.redis_url, backend=settings.redis_url)

celery_app.conf.task_routes = {"backend.workers.tasks.*": {"queue": "applications"}}


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def run_application(self, run_id: str, job_url: str, profile: dict) -> dict:
    import asyncio

    import anthropic

    from backend.agents.orchestrator import Orchestrator
    from backend.services.browser import BrowserService
    from backend.services.storage import StorageService

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    storage = StorageService()
    browser = BrowserService()
    orchestrator = Orchestrator(client, storage, browser)

    try:
        return asyncio.get_event_loop().run_until_complete(
            orchestrator.run(job_url, profile, run_id)
        )
    except Exception as exc:
        raise self.retry(exc=exc)
