# Claude 官方接口（Anthropic）。
# 自带搜索和读网页：由 Anthropic 的服务器去做，搜索每 1000 次另收 10 美元，读网页只算 token。
# max_uses 是"这一轮最多用几次"，由服务器替我们数，超了它自己停。
# 写法来自官方文档：
#   https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool
#   https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool
#
# 要知道的花费（2026-11-24 实测，主 bot 空白模板，问一句不需要搜的话）：
#   请求里不带搜索和读网页                 4412 个 token
#   带我们自己写的两个工具                 多 433
#   带服务器的两个，不写 allowed_callers   多 6120
#   带服务器的两个，写 ["direct"]          多 3200
# 也就是说：只要清单里放了服务器的搜索，哪怕这句话根本不用搜，每次调用都要多发几千个 token。
# 不写 allowed_callers 时，它默认会让模型先写一段代码去筛搜索结果（要带上一整套执行代码的说明），所以更贵。
# 这里写 ["direct"]：模型直接搜、直接看结果，固定开销少一半。真的搜一次，搜回来的内容还要另算 token。

NAME = "Claude"

SERVER_TOOLS = {
    "web_search": {"type": "web_search_20260209", "name": "web_search", "max_uses": 5, "allowed_callers": ["direct"]},
    "web_fetch": {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 5, "allowed_callers": ["direct"]},
}

CACHE_MARKS = True      # 认提示词缓存的标记
