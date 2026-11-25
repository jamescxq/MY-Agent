import json
import urllib.error
import urllib.request

# 搜索服务：一家一个文件。想多支持一家，在这个文件夹里加一个文件，再在下面的 PROVIDERS 里加一行。
#
# 每个文件要有三样：
#   NAME          给人看的名字
#   ENV           它的密钥在 .env 里叫什么
#   search(query, count, key)   去搜，返回一个列表，每条是 {"title": 标题, "url": 网址, "snippet": 摘要}
#                               出问题抛 SearchError，里面是给模型看的原因
# 密钥只从 .env 读（见 config.py 的 SEARCH_KEYS），不写在代码里。


class SearchError(Exception):
    pass


def post_json(url, payload, headers=None, timeout=20):
    """往搜索服务发一个 JSON 请求，返回它回的 JSON。各家共用。网址是写死的搜索服务地址，不是模型给的，所以不用过网址门禁。"""
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "Accept": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        reasons = {401: "密钥不对", 402: "额度用完了", 403: "没有权限，或者余额不足", 429: "请求太频繁"}
        raise SearchError(reasons.get(exc.code, f"搜索服务回了错误 {exc.code}")) from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SearchError(f"连不上搜索服务（{type(exc).__name__}）") from None
    except ValueError:
        raise SearchError("搜索服务回的不是 JSON") from None


from . import tavily, bocha      # 放在下面：它们要用到上面的 SearchError 和 post_json

PROVIDERS = {"tavily": tavily, "bocha": bocha}
