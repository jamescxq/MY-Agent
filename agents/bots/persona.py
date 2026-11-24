import json
from agents import loop
from agents.capabilities import load_packs
from agents.prompt.texts import prompt_text

# 新建 Agent 时，根据名字起草一份人设。
#
# 分工：
#   - 模型只做一件事：看名字，填几个短的字段（角色、性格、说话风格、一句话说明、相关的能力包）。
#     它不拿工具，也不直接写文件。
#   - 代码负责把这几个字段填进 AGENT.md 的模板里（fill_persona）。
# 这样人设文件的格式永远是模板的格式，模型写歪了也只是某一栏的内容不好，不会把文件写坏。
# 模型没调通、回的不是 JSON，都返回 None：Agent 照样建好，只是人设还是空白模板。

# AGENT.md 模板里等着填的几处占位文字。和 templates/bot/AGENT.md 里的要一字不差
ROLE_HINT = "*(AI助理、智能管家、技术顾问等)*"
TRAIT_HINT = "*(友好、专业、幽默、严谨等)*"
STYLE_HINT = """*(描述你如何与用户交流：)*
- 使用什么样的语言风格？（正式/轻松/幽默）
- 回复长度偏好？（简洁/详细）
- 是否使用表情符号？"""
INTRO_HINT = "*在首次对话时与用户一起填写这个文件，定义你的身份和性格。*"
INTRO_DONE = "*这份人设是新建时根据名字写的初稿。用户想改，就用 edit_file 改这个文件。*"

GENERAL_ROLE = "通用助手"
TRACE_NAME = "起草人设"         # 用量记录里，起草人设的那次调用记在这个名字下

SYSTEM = prompt_text("persona")     # 起草人设时给模型的说明。原文在 templates/prompts/persona.md


def pack_list():
    """可以选的能力包：每个 Agent 都有的不用选，不列出来。"""
    return [pack for pack in load_packs() if not pack.always]


def one_line(value, limit):
    """把模型给的一段话变成一行，并且不超过 limit 个字。"""
    return " ".join(str(value).split())[:limit]


def read_reply(text, pack_ids):
    """从模型的回复里取出人设。回复不是 JSON、或者缺了要紧的字段，返回 None。"""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None

    domain = data.get("domain") is True
    role = one_line(data.get("role", ""), 20) if domain else GENERAL_ROLE
    if not role:
        return None
    packs = data.get("packs")
    return {
        "domain": domain,
        "role": role,
        "personality": one_line(data.get("personality", ""), 30) or "友好、认真",
        "style": one_line(data.get("style", ""), 60) or "简洁清楚，有话直说",
        "description": one_line(data.get("description", ""), 40),
        # 只留清单里真有的编号，模型自己编的丢掉
        "packs": [pack_id for pack_id in packs if pack_id in pack_ids] if isinstance(packs, list) else [],
    }


def draft_persona(name, description=""):
    """调一次模型，根据名字起草人设。返回一个字典（见 read_reply）；没写成返回 None。"""
    packs = pack_list()
    lines = [f"名字：{name}", f"用户的补充说明：{description or '（没有）'}", "", "能力包清单："]
    for pack in packs:
        state = "可用" if pack.available else "还没接入"
        lines.append(f"- {pack.id}：{pack.name}，{pack.description}（{state}）")
    response = loop.call_model(                  # 和对话走同一个入口，所以这次调用也会记进用量
        TRACE_NAME, 1,                           # 这时候新 Agent 还没建出来，没有编号，用量记在这个名字下
        max_tokens=1024,
        system=SYSTEM,
        messages=[{"role": "user", "content": "\n".join(lines)}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    return read_reply(text, [pack.id for pack in packs])


def fill_persona(folder, persona):
    """把起草好的人设填进这个 Agent 的 AGENT.md。只换模板里的占位文字，别的不动。"""
    path = folder / "AGENT.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace(ROLE_HINT, persona["role"])
    text = text.replace(TRAIT_HINT, persona["personality"])
    text = text.replace(STYLE_HINT, persona["style"])
    text = text.replace(INTRO_HINT, INTRO_DONE)
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    # 不调模型：只试"读回复"和"填模板"这两步
    ids = ["notify", "apply", "email"]
    good = '好的，这是人设：{"domain": true, "role": "英语老师", "personality": "耐心、幽默", "style": "多用例句\\n少讲术语", "description": "陪你练英语", "packs": ["apply", "编的"]}'
    print(read_reply(good, ids))            # 应该：role 是 英语老师，style 变成一行，packs 只剩 ['apply']
    print(read_reply('{"domain": false, "role": "随便写的", "packs": "notify"}', ids))   # 应该：role 是 通用助手，packs 是 []
    print(read_reply("我不会写 JSON", ids))   # 应该：None
    print(read_reply('{"domain": true}', ids))   # 应该：None，没有角色

    import tempfile
    from pathlib import Path
    from config import TEMPLATES

    for hint in (ROLE_HINT, TRAIT_HINT, STYLE_HINT, INTRO_HINT):     # 模板改了占位文字，这里要跟着改
        assert hint in (TEMPLATES / "bot" / "AGENT.md").read_text(encoding="utf-8"), hint
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "AGENT.md").write_text((TEMPLATES / "bot" / "AGENT.md").read_text(encoding="utf-8"), encoding="utf-8")
        fill_persona(folder, read_reply(good, ids))
        print((folder / "AGENT.md").read_text(encoding="utf-8")[:330])   # 应该：角色、性格、交流风格都填上了
