# DeepSeek 的"兼容 Claude 接口"入口（https://api.deepseek.com/anthropic）。
# 下面是照它的文档写的（2026-11-24 读的），还没有实际连过：
#   https://api-docs.deepseek.com/guides/anthropic_api
#   https://api-docs.deepseek.com/guides/web_tools
#
# 它也有接口自带的搜索和读网页（deepseek_web_search、deepseek_read_url），但文档写明：
# 这两个不能和别的工具一起声明，用过它们的回复也不能接着往下聊。
# 我们的 Agent 总是带着读写文件这些工具，所以用不上，这里留空。搜索走我们自己写的工具。

NAME = "DeepSeek"

SERVER_TOOLS = {}

CACHE_MARKS = False     # 缓存标记会被忽略（不报错）。它自己会自动缓存
