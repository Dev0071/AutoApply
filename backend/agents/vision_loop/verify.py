from playwright.async_api import Page


async def verify_action(page: Page, field_name: str, expected_value: str) -> bool:
    try:
        locator = page.get_by_label(field_name)
        actual = await locator.input_value(timeout=1000)
        return actual.strip() == expected_value.strip()
    except Exception:
        return False
