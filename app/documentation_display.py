"""Resolve how documentation is shown: live iframe vs Firecrawl markdown fallback."""

from __future__ import annotations

import html
import logging
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import bleach
import markdown
from firecrawl import Firecrawl

from flask import current_app

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DocumentationDisplayResult:
    documentation_url: str
    use_fallback: bool
    fallback_html: str


def resolve_documentation_display(documentation_url: str) -> DocumentationDisplayResult:
    raw = documentation_url if isinstance(documentation_url, str) else ""
    url = raw.strip()

    empty_html = (
        '<!DOCTYPE html><html lang="en">'
        '<head><meta charset="utf-8"><title></title></head><body></body></html>'
    )

    if not url or not _is_valid_http_documentation_url(url):
        return DocumentationDisplayResult(
            documentation_url=url,
            use_fallback=False,
            fallback_html=empty_html,
        )

    if _is_iframe_embeddable_url(url):
        return DocumentationDisplayResult(
            documentation_url=url,
            use_fallback=False,
            fallback_html=empty_html,
        )

    api_key = current_app.config.get("FIRECRAWL_API_KEY")
    if not api_key:
        raise RuntimeError(
            "FIRECRAWL_API_KEY is required when the documentation URL is not iframe-embeddable. "
            "Set app.config['FIRECRAWL_API_KEY'] (see create_app)."
        )

    try:
        fc = Firecrawl(api_key=api_key)
        doc = fc.scrape(url, formats=["markdown"])
        md = (doc.markdown or "").strip()

    except Exception:
        logger.exception("Firecrawl scrape failed for %s", url)
        hint = "Could not fetch documentation for preview. Open the original link in a new tab."
        return DocumentationDisplayResult(
            documentation_url=url,
            use_fallback=True,
            fallback_html=_html_document_from_body(f"<p>{html.escape(hint)}</p>"),
        )

    if not md:
        empty_msg = "No markdown content was returned for this page."
        return DocumentationDisplayResult(
            documentation_url=url,
            use_fallback=True,
            fallback_html=_html_document_from_body(f"<p>{html.escape(empty_msg)}</p>"),
        )

    raw_html = _markdown_to_html(md)
    safe_html = _sanitize_doc_html(raw_html)
    return DocumentationDisplayResult(
        documentation_url=url,
        use_fallback=True,
        fallback_html=_html_document_from_body(safe_html),
    )


# Helpers: test for iframe embeddability

def _parse_csp_frame_ancestors(csp_header: str) -> list[str] | None:
    if not csp_header:
        return None
    directives = [d.strip() for d in csp_header.split(";") if d.strip()]
    for d in directives:
        if d.lower().startswith("frame-ancestors"):
            parts = d.split()
            return [p.strip() for p in parts[1:]]
    return None


def _is_iframe_embeddable_url(url: str) -> bool:
    if not isinstance(url, str) or not url.strip():
        return False
    url = url.strip()

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False

    req = Request(
        url,
        method="HEAD",
        headers={
            "User-Agent": "interactive-docs/1.0 (+iframe-embeddability-preflight)",
            "Accept": "*/*",
        },
    )

    try:
        with urlopen(req, timeout=2.0) as resp:
            headers = resp.headers
    except HTTPError:
        return False
    except URLError:
        return False
    except Exception:
        return False

    xfo = (headers.get("X-Frame-Options") or "").strip().lower()
    if xfo:
        if "deny" in xfo:
            return False
        if "sameorigin" in xfo:
            return False

    csp = headers.get("Content-Security-Policy") or headers.get(
        "Content-Security-Policy-Report-Only"
    )
    frame_ancestors = _parse_csp_frame_ancestors(csp or "")
    if frame_ancestors is not None:
        toks = [t.strip() for t in frame_ancestors if t.strip()]
        lower = [t.lower() for t in toks]

        if "'none'" in lower:
            return False
        if "*" in toks:
            return True

        return False

    return True


# Helpers: markdown → HTML for iframe srcdoc
#
# Pipeline (when Firecrawl fallback is used): Firecrawl returns page text as Markdown.
# We convert with the third-party markdown library (fenced code, GFM-style tables,
# line breaks), then run bleach.clean with an explicit tag/attribute/protocol
# allowlist so arbitrary MD/HTML from the crawl cannot execute in the embedded document.
# Finally ``_html_document_from_body`` wraps the fragment in a minimal full HTML document
# (charset, viewport, light styling).

def _is_valid_http_documentation_url(url: str) -> bool:
    parsed = urlparse(url.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _markdown_to_html(md: str) -> str:
    return markdown.markdown(
        md,
        extensions=["fenced_code", "tables", "nl2br"],
        output_format="html",
    )


_DOC_TAGS = frozenset({"p", "br", "hr", "div", "span", "h1", "h2", "h3", "h4",
                       "h5", "h6", "ul", "ol", "li", "blockquote", "pre", "code",
                       "strong", "em", "b", "i", "a", "img", "table", "thead", 
                       "tbody", "tr", "th", "td", "sup", "sub", "del", "ins"})

_DOC_ATTRS = {
    "a": ["href", "title", "rel"],
    "img": ["src", "alt", "title", "loading"],
    "th": ["colspan", "rowspan", "align"],
    "td": ["colspan", "rowspan", "align"],
    "*": ["class", "id"],
}


def _sanitize_doc_html(fragment: str) -> str:
    return bleach.clean(
        fragment,
        tags=_DOC_TAGS,
        attributes=_DOC_ATTRS,
        protocols=("http", "https"),
        strip=True,
    )


def _html_document_from_body(inner_html: str) -> str:
    """Minimal full document wrapping sanitized body HTML (no external template file)."""
    return (
        "<!DOCTYPE html><html lang=\"en\"><head>"
        '<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>Documentation</title>"
        "<style>"
        "body{font-family:system-ui,-apple-system,sans-serif;line-height:1.5;margin:1rem;max-width:52rem;}"
        "pre{overflow:auto;padding:0.75rem;background:#f4f4f5;border-radius:0.375rem;}"
        "code{font-family:ui-monospace,monospace;font-size:0.9em;}"
        "table{border-collapse:collapse;width:100%;}"
        "th,td{border:1px solid #ccc;padding:0.35rem 0.5rem;}"
        "@media (prefers-color-scheme: dark){"
        "body{background:#121212;color:#e8e8e8;}"
        "pre{background:#1e1e1e;}"
        "th,td{border-color:#444;}"
        "}"
        "</style></head><body>"
        f"{inner_html}</body></html>"
    )
