import os
from . import claude, deepseek, other

# 各家模型的接口不一样的地方，一家一个文件。想多支持一家，在这个文件夹里加一个文件，再在下面加一行判断。
#
# 每个文件要有：
#   NAME           给人看的名字
#   SERVER_TOOLS   这家接口自带、由它的服务器去执行的工具：{"web_search": 请求里要带的那几行, ...}
#                  没有就是空的。自带的搜索不在我们电脑上跑，也不经过我们的工具门禁
#   CACHE_MARKS    这家认不认"提示词缓存"的标记
#
# 注意：这里只记"接口有什么不同"。用哪个模型（MODEL）、地址和密钥，还是在 .env 里。


def vendor():
    """现在连的是哪一家。看 .env 里的 ANTHROPIC_BASE_URL：没填就是 Claude 官方。认不出来的，当成"什么都不自带"。"""
    base = os.environ.get("ANTHROPIC_BASE_URL", "").lower()
    if not base or "anthropic.com" in base:
        return claude
    if "deepseek" in base:
        return deepseek
    return other
