from __future__ import annotations

import re

from playwright.async_api import Page

# Tri-state result: True = value confirmed, False = confirmed mismatch,
# None = the field could not be located, so nothing is known.
#
# The distinction matters for cost: the loop escalates to the expensive model
# only on confirmed mismatches. Treating "not found" as failure would escalate
# on every form whose labels don't match the model's field naming.

_ATTRIBUTE_TEMPLATES = (
    '[name="{key}"]',
    "#{key}",
    '[aria-label="{key}"]',
)


def _variants(field_name: str) -> list[str]:
    """A model-supplied field name may be snake_case ('first_name') while the
    DOM label reads 'First Name *'. Try the common renderings of both."""
    raw = field_name.strip()
    spaced = re.sub(r"[_-]+", " ", raw)
    return list(dict.fromkeys([raw, spaced, spaced.title(), raw.lower().replace(" ", "_")]))


async def verify_action(
    page: Page, field_name: str, expected_value: str
) -> bool | None:
    """Post-action DOM verification only — NEVER used for targeting.

    Returns True if the field holds the expected value, False if it holds
    something else, and None if the field could not be located at all.
    """
    if not field_name:
        return None

    expected = expected_value.strip()
    variants = _variants(field_name)

    def candidates():
        """Yield locator factories lazily — a malformed selector must not
        abort the whole verification, only skip that strategy."""
        for key in variants:
            yield lambda k=key: page.get_by_label(k, exact=False)
            yield lambda k=key: page.get_by_placeholder(k, exact=False)
        for template in _ATTRIBUTE_TEMPLATES:
            for key in variants:
                if template.startswith("#") and " " in key:
                    continue  # not a valid id
                yield lambda t=template, k=key: page.locator(t.format(key=k))

    for make_locator in candidates():
        try:
            actual = await make_locator().first.input_value(timeout=500)
        except Exception:
            continue
        return actual.strip() == expected

    return None
