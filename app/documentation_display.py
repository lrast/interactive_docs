"""Resolve how documentation is shown: live iframe vs Firecrawl markdown fallback."""

from __future__ import annotations

import html
import logging
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import bleach
import markdown
from firecrawl import Firecrawl

logger = logging.getLogger(__name__)

MINIMAL_EMPTY_HTML = (
    '<!DOCTYPE html><html lang="en">'
    '<head><meta charset="utf-8"><title></title></head><body></body></html>'
)

# --- DEBUG: subject to later deletion — last Firecrawl markdown scrape written for inspection.
_DEBUG_DOCS_MD_PATH = Path(__file__).resolve().parent.parent / "debug" / "docs.md"


_DOC_TAGS = frozenset(
    {
        "p",
        "br",
        "hr",
        "div",
        "span",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "ul",
        "ol",
        "li",
        "blockquote",
        "pre",
        "code",
        "strong",
        "em",
        "b",
        "i",
        "a",
        "img",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
        "sup",
        "sub",
        "del",
        "ins",
    }
)

_DOC_ATTRS = {
    "a": ["href", "title", "rel"],
    "img": ["src", "alt", "title", "loading"],
    "th": ["colspan", "rowspan", "align"],
    "td": ["colspan", "rowspan", "align"],
    "*": ["class", "id"],
}


@dataclass(frozen=True)
class DocumentationDisplayResult:
    documentation_url: str
    use_fallback: bool
    fallback_html: str


def resolve_documentation_display(documentation_url: str) -> DocumentationDisplayResult:
    raw = documentation_url if isinstance(documentation_url, str) else ""
    url = raw.strip()
    if not url or not _is_valid_http_documentation_url(url):
        return DocumentationDisplayResult(
            documentation_url=url,
            use_fallback=False,
            fallback_html=MINIMAL_EMPTY_HTML,
        )

    if _is_iframe_embeddable_url(url):
        return DocumentationDisplayResult(
            documentation_url=url,
            use_fallback=False,
            fallback_html=MINIMAL_EMPTY_HTML,
        )

    api_key = _get_firecrawl_api_key()
    if not api_key:
        raise RuntimeError(
            "FIRECRAWL_API_KEY is required when the documentation URL is not iframe-embeddable. "
            "Set app.config['FIRECRAWL_API_KEY'] while running inside a Flask application context "
            "(see create_app)."
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

    # DEBUG: subject to later deletion
    _write_debug_scrape_markdown(md)

    raw_html = _markdown_to_html(md)
    safe_html = _sanitize_doc_html(raw_html)
    return DocumentationDisplayResult(
        documentation_url=url,
        use_fallback=True,
        fallback_html=_html_document_from_body(safe_html),
    )


def _is_valid_http_documentation_url(url: str) -> bool:
    parsed = urlparse(url.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _get_firecrawl_api_key() -> str | None:
    from flask import current_app, has_app_context

    if not has_app_context():
        return None
    cfg = current_app.config.get("FIRECRAWL_API_KEY")
    if isinstance(cfg, str) and cfg.strip():
        return cfg.strip()
    return None


def _markdown_to_html(md: str) -> str:
    return markdown.markdown(
        md,
        extensions=["fenced_code", "tables", "nl2br"],
        output_format="html",
    )


def _sanitize_doc_html(fragment: str) -> str:
    return bleach.clean(
        fragment,
        tags=_DOC_TAGS,
        attributes=_DOC_ATTRS,
        protocols=("http", "https", "mailto"),
        strip=True,
    )


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


def _write_debug_scrape_markdown(md: str) -> None:
    """DEBUG: subject to later deletion — dump raw markdown for local inspection."""
    try:
        _DEBUG_DOCS_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
        _DEBUG_DOCS_MD_PATH.write_text(md, encoding="utf-8")
    except OSError:
        logger.debug("Could not write debug markdown to %s", _DEBUG_DOCS_MD_PATH, exc_info=True)
