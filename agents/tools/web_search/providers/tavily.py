from . import SearchError, post_json

# Tavily：https://tavily.com 。请求和返回的写法参考了 CowAgent 的 agent/tools/web_search/web_search.py。

NAME = "Tavily"
ENV = "TAVILY_API_KEY"


def search(query, count, key):
    data = post_json("https://api.tavily.com/search", {
        "api_key": key,
        "query": query,
        "max_results": count,
        "search_depth": "basic",
        "include_answer": False,
    })
    results = data.get("results")
    if results is None:
        raise SearchError("Tavily 回的内容里没有结果")
    return [{"title": item.get("title", ""), "url": item.get("url", ""), "snippet": item.get("content") or item.get("snippet", "")} for item in results]
