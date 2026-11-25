from dataclasses import dataclass, field
import config
from config import TEMPLATES
from agents.tools import TOOLS
from agents.tools.web_search import search_ready
from agents.models import vendor

# 能力包：一个能力一个文件夹，在 templates/capabilities/ 下面，里面是一份 CAPABILITY.md。
# 这个文件负责两件事：
#   1. 算出一个 Agent 能拿到哪些工具（没启用的能力包，工具根本不交给模型）
#   2. 生成一份"你现在能做什么"的清单拼进提示词（清单由代码给，不让模型自己编）
#
# 现在代码只读 CAPABILITY.md 开头两条横线之间的几行。下面的正文（风险规则、要收集的资料）
# 先是写给人看的，做到对应功能时再用。

PACKS_DIR = TEMPLATES / "capabilities"
BASE_TOOLS = ["get_time"]         # 不属于任何能力包、每个 Agent 都有的工具
WEB_TOOLS = ("web_search", "web_fetch")     # 搜索和读网页有两条路，走哪条见 web_mode()
MAIN = "main"                     # 主 bot：所有能用的能力包默认都开着


@dataclass
class Pack:
    id: str                       # 文件夹名，比如 notes
    name: str                     # 给人看的名字，比如 笔记与记忆
    description: str = ""         # 一句话说明
    tools: list = field(default_factory=list)   # 这个能力带来哪些工具
    available: bool = False       # 接好了没有。False 就是"还没接入"
    always: bool = False          # True 表示每个 Agent 都有，不能关


def read_header(text):
    """读 CAPABILITY.md 开头两条 --- 之间的内容，每行是"名字: 值"，返回字典。"""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    header = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, _, value = line.partition(":")
        header[key.strip()] = value.strip()
    return header


def load_packs(folder=PACKS_DIR):
    """读出全部能力包。顺序：每个 Agent 都有的 → 能用的 → 还没接入的。"""
    packs = []
    for item in sorted(folder.iterdir()):
        path = item / "CAPABILITY.md"
        if not path.is_file():
            continue
        header = read_header(path.read_text(encoding="utf-8"))
        packs.append(Pack(
            id=item.name,
            name=header.get("name", item.name),
            description=header.get("description", ""),
            tools=[name.strip() for name in header.get("tools", "").split(",") if name.strip()],
            available=header.get("status") == "可用",
            always=header.get("always") == "是",
        ))
    packs.sort(key=lambda pack: (not pack.always, not pack.available))
    return packs


def enabled_ids(bot_id, chosen):
    """这个 Agent 启用了哪些能力包。chosen 是用户给它打开的那些（存在花名册里）。

    还没接入的不算；每个 Agent 都有的一定算。
    主 bot 特殊一点：用户还没给它选过（chosen 是空的）时，所有能用的都开着；
    选过以后就按选的来，和别的 Agent 一样。
    怎么区分"没选过"和"选了但全关掉"：给主 bot 存的时候，把每个 Agent 都有的那几项也一起存，
    所以只要选过，这份名单就不会是空的。
    """
    all_on = bot_id == MAIN and not chosen
    ids = []
    for pack in load_packs():
        if not pack.available:
            continue
        if pack.always or all_on or pack.id in chosen:
            ids.append(pack.id)
    return ids


def web_mode():
    """搜索和读网页现在走哪条路。own：我们自己写的工具；server：让模型那边的服务器去做。

    由 config.py 的 WEB_MODE 决定。auto（默认）时：配了搜索服务的密钥就用自己的；
    没配、但现在连的这家模型接口自带搜索（见 agents/models/），就让服务器去搜；两样都没有也用自己的
    （这时搜索工具会如实告诉模型"还没配置"，读网页照常能用）。
    """
    has_server = bool(vendor().SERVER_TOOLS)
    if config.WEB_MODE == "own":
        return "own"
    if config.WEB_MODE == "server":
        return "server" if has_server else "own"
    return "own" if search_ready() or not has_server else "server"


def tools_for(ctx):
    """这个 Agent 能拿到的工具（交给模型的那份清单）。

    搜索和读网页走"让服务器去做"那条路时，清单里放的不是我们自己的工具说明，
    而是那家接口规定的那几行（告诉服务器：这一轮允许你搜、允许你读网页）。
    """
    names = set(BASE_TOOLS)
    for pack in load_packs():
        if pack.id in ctx.packs:
            names.update(pack.tools)
    server = vendor().SERVER_TOOLS if web_mode() == "server" else {}
    return [server.get(tool["name"], tool) if tool["name"] in WEB_TOOLS else tool for tool in TOOLS if tool["name"] in names]


def capability_text(ctx):
    """拼进提示词的能力清单。"""
    on, off, missing = [], [], []
    for pack in load_packs():
        line = f"- {pack.name}：{pack.description}"
        if not pack.available:
            missing.append(line)
        elif pack.id in ctx.packs:
            on.append(line + f"（工具：{'、'.join(pack.tools)}）")
        else:
            off.append(line)

    parts = [
        "<capabilities>",
        "这份清单由系统生成，说明你现在能做什么。以它为准，不要自己编。",
        "",
        "不需要工具的事（聊天、解释、写文字、出主意）你本来就能做。",
        "",
        "已启用的能力：",
        *on,
    ]
    if off:
        parts += ["", "没有启用的能力（用户输入 /packs 可以打开）：", *off]
    if missing:
        parts += ["", "还没接入的能力（现在做不了）：", *missing]
    parts += [
        "",
        "介绍自己能做什么时，只说“已启用的能力”。"
        "用户要你做“没有启用”或“还没接入”的事，如实说现在做不了，并说明是哪一种；"
        "不要假装做了，也不要承诺以后一定会有。",
        "</capabilities>",
    ]
    return "\n".join(parts)


if __name__ == "__main__":
    from pathlib import Path
    from agents.bots import Ctx

    for pack in load_packs():
        print(pack.id, pack.name, pack.tools, "能用" if pack.available else "还没接入", "必有" if pack.always else "")

    print(enabled_ids("main", []))            # 应该：['notes', 'notify']，主 bot 没选过时全开
    print(enabled_ids("main", ["notes"]))     # 应该：['notes']，主 bot 选过以后按选的来
    print(enabled_ids("bot-1", []))           # 应该：['notes']，只有必有的
    print(enabled_ids("bot-1", ["notify"]))   # 应该：['notes', 'notify']
    print(enabled_ids("bot-1", ["email"]))    # 应该：['notes']，还没接入的开不了

    ctx = Ctx(bot_id="bot-1", folder=Path("x"), user_folder=Path("y"), packs=enabled_ids("bot-1", []))
    print([tool["name"] for tool in tools_for(ctx)])    # 应该：没有 notify
    print(capability_text(ctx))
