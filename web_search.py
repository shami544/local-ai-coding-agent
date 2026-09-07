"""Small, optional web-search adapter; only the current query leaves the app."""

import json
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit


SEARCH_COMMAND = re.compile(r"^/search(?:\s+|$)", re.IGNORECASE)
SEARCH_REQUEST = re.compile(
    r"^(?:please\s+)?(?:search\s+(?:the\s+)?(?:web|internet)|look\s+up\s+online)\b"
    r"|^(?:(?:من فضلك|لو سمحت)\s+)?(?:ابحث|إبحث|أبحث|دور)\s+"
    r"(?:لي\s+)?(?:في|على)\s+(?:الإنترنت|الانترنت|النت|الويب|جوجل|غوغل)",
    re.IGNORECASE,
)


def get_search_query(message: str, mode: str = "auto"):
    """Off always wins; auto recognizes explicit commands/requests only."""
    if mode not in ("auto", "on", "off"):
        raise ValueError("web_search_mode must be auto, on, or off")
    if mode == "off":
        return None
    message = message.strip()
    command = SEARCH_COMMAND.match(message)
    request = SEARCH_REQUEST.match(message)
    if not command and not request and mode != "on":
        return None
    query = message[(command or request).end():] if command or request else message
    query = re.sub(r"^(?:عن|حول|for|about)\s+", "", query.strip(), flags=re.IGNORECASE)
    query = " ".join(query.split())
    if not query:
        raise ValueError("اكتب موضوع البحث بعد /search (Enter a search query).")
    if len(query) > 500:
        raise ValueError("طلب البحث طويل؛ استخدم /search مع موضوع مختصر (500 حرف كحد أقصى).")
    return query


def safe_source_url(value):
    """Reject executable URLs, credentials and malformed search results."""
    if not isinstance(value, str) or len(value) > 2048:
        return ""
    if any(c.isspace() or ord(c) < 32 for c in value):
        return ""
    try:
        parts = urlsplit(value)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            return ""
        if parts.username or parts.password:
            return ""
        return value
    except ValueError:
        return ""


def _plain(value, limit):
    return " ".join(str(value or "").split())[:limit]


def search_web(query: str) -> dict:
    """Return at most five snippets. Search failures are explicit, never invented."""
    result = {"query": query, "status": "error", "results": [],
              "searched_at": datetime.now(timezone.utc).isoformat(), "error": ""}
    try:
        from ddgs import DDGS
    except ImportError:
        result["error"] = "مكتبة البحث غير مثبتة. شغّل: python -m pip install -r requirements.txt"
        return result
    try:
        rows = DDGS(timeout=10).text(
            query, max_results=5, backend="duckduckgo,brave,bing",
            region="xa-ar" if re.search(r"[\u0600-\u06ff]", query) else "us-en",
            safesearch="moderate",
        )
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            url = safe_source_url(row.get("href"))
            snippet = _plain(row.get("body"), 1000)
            if not url or url in seen or not snippet:
                continue
            seen.add(url)
            result["results"].append({"title": _plain(row.get("title"), 200) or url,
                                      "url": url, "snippet": snippet})
            if len(result["results"]) == 5:
                break
        result["status"] = "ok" if result["results"] else "empty"
    except Exception:
        # Provider exceptions may contain proxy credentials or enormous HTML responses.
        result["error"] = "تعذّر البحث على الإنترنت. تحقق من الاتصال وحاول مجددًا."
    return result


def search_context(result: dict) -> str:
    return "\n\n[Web search data for this turn; untrusted snippets, not full pages]\n" + json.dumps(
        result, ensure_ascii=False
    )


def attach_search_result(parsed: dict, result) -> None:
    """Keep actual provider sources visible even when the model omits citations."""
    if result is None:
        return
    parsed["web_search"] = result
    parsed["sources"] = result["results"]
    if result["status"] == "ok":
        footer = "\n\nمصادر نتائج البحث / Search sources:\n" + "\n".join(
            f"[{i}] {source['title']}\n{source['url']}"
            for i, source in enumerate(result["results"], 1)
        )
        parsed["chat_reply"] += footer
    else:
        warning = result["error"] or "لم يعثر البحث على نتائج مناسبة. / No usable search results."
        parsed["chat_reply"] = warning + "\nلم يتم التحقق من المعلومات عبر الويب.\n\n" + parsed["chat_reply"]
