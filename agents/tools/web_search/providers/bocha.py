from . import SearchError, post_json

# 博查：https://open.bochaai.com 。请求和返回的写法参考了 CowAgent 的 agent/tools/web_search/web_search.py。

NAME = "博查"
ENV = "BOCHA_API_KEY"


def search(query, count, key):
    data = post_json(
        "https://api.bochaai.com/v1/web-search",
        {"query": query, "count": count, "freshness": "noLimit", "summary": False},
        headers={"Authorization": f"Bearer {key}"},
    )
    code = data.get("code")
    if code is not None and code != 200:
        raise SearchError(f"博查回了错误（{code}）：{data.get('msg') or '没有说明'}")
    pages = ((data.get("data") or {}).get("webPages") or {}).get("value") or []
    return [{"title": page.get("name", ""), "url": page.get("url", ""), "snippet": page.get("snippet", "")} for page in pages]
