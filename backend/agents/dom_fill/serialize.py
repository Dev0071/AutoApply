"""Serialize the live page's form into compact text for the field mapper.

No hardcoded selectors: this reads whatever form elements exist on the page
at runtime, in DOM order. `ref` is the element's index within the generic
form-element query, so the executor can re-locate the same element with
`page.locator(FORM_ELEMENT_SELECTOR).nth(ref)`.
"""
from __future__ import annotations

from playwright.async_api import Page

FORM_ELEMENT_SELECTOR = "input, select, textarea"

_SERIALIZE_JS = """
els => els.map((el, i) => {
  const style = window.getComputedStyle(el);
  const visible = el.offsetParent !== null
    && style.visibility !== 'hidden'
    && style.display !== 'none';
  const labelEl = el.labels && el.labels.length ? el.labels[0] : null;
  const label = (labelEl && labelEl.innerText.trim())
    || el.getAttribute('aria-label')
    || el.placeholder
    || el.name
    || el.id
    || '';
  return {
    ref: i,
    tag: el.tagName.toLowerCase(),
    input_type: (el.type || '').toLowerCase(),
    label: label,
    required: !!el.required,
    value: el.value || '',
    options: el.tagName === 'SELECT'
      ? Array.from(el.options).map(o => o.label)
      : [],
    visible: visible,
  };
})
"""

_NON_FILLABLE_TYPES = {"hidden", "submit", "button", "reset", "image"}


async def serialize_form(page: Page) -> list[dict]:
    """Return the visible, fillable form fields on the current page."""
    raw = await page.eval_on_selector_all(FORM_ELEMENT_SELECTOR, _SERIALIZE_JS)
    return [
        f for f in raw
        if f["visible"] and f["input_type"] not in _NON_FILLABLE_TYPES
    ]
