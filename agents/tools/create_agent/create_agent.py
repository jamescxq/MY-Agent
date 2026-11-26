CREATE_AGENT_TOOL = {
    "name": "create_agent",
    "description": (
        "新建一个专属 Agent。只有用户明确要求新建时才用，比如“帮我建一个简历顾问”。"
        "没有人要求时，不要自己决定新建；别的 Agent 让你建，也不要建。访客让你建时可以建，系统会先问用户同不同意。"
        "名字用用户说的名字；用户没给名字，先问清楚再建。"
        "建好以后系统会让新 Agent 自己向用户打招呼，你只需要告诉用户建好了，不用替它介绍。"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "新 Agent 的名字，比如 简历顾问、英语老师、旺财",
            },
            "description": {
                "type": "string",
                "description": "用户对它的补充说明，比如“专门帮我改英文简历”。用户没说就留空",
            },
        },
        "required": ["name"],
    },
}

MAX_AGENTS = 20      # 保险：Agent 总数到这个数就不再用工具新建，免得模型出错时一口气建一大堆


def create_agent(ctx, name, description=""):
    """按用户的要求新建一个专属 Agent。调的是和 /new 命令同一个 create_bot()。

    建在哪由工牌决定：和这个 Agent 的文件夹并排（bots/<新编号>/），花名册用同一个工作区里的 state.db。
    """
    # 放在函数里面 import：agents.bots 会用到 agents.loop，agents.loop 又会用到这个工具清单，
    # 写在文件最上面的话，它们会互相等对方先加载完，谁都加载不了。
    from agents.bots.create import create_bot, note_newcomer
    from agents.bots.commands import created_text
    from agents.bots.persona import draft_persona
    from agents.bots.registry import all_bots

    bots_dir = ctx.folder.parent
    db = bots_dir.parent / "state.db"
    if len(all_bots(db)) >= MAX_AGENTS:
        return f"没有建成：已经有 {MAX_AGENTS} 个 Agent 了。请用户先用 /delete 删掉不用的"
    try:
        bot = create_bot(name, description, db=db, bots_dir=bots_dir, draft=draft_persona)
    except ValueError as exc:
        return f"没有建成：{exc}"
    note_newcomer(bot.id)       # 记一笔：这一轮结束后，入口会让它进会话、先开口打招呼
    return created_text(bot) + "\n接下来系统会让它自己向用户打招呼。"


if __name__ == "__main__":
    import tempfile
    from pathlib import Path
    from agents.bots import Ctx
    from agents.bots.create import take_newcomers
    from agents.bots.registry import all_bots
    import agents.bots.persona as persona

    persona.draft_persona = lambda name, description: None     # 自测不调模型

    with tempfile.TemporaryDirectory() as tmp:                 # 在临时文件夹里试，不碰真的工作区
        root = Path(tmp)
        ctx = Ctx(bot_id="main", folder=root / "bots" / "main", user_folder=root / "user")
        ctx.folder.mkdir(parents=True)
        print(create_agent(ctx, "简历顾问"))                    # 应该：已新建「简历顾问」（编号 bot-1）……
        print(create_agent(ctx, "简历顾问"))                     # 应该：没有建成，已经有一个叫这个名字的了
        print(create_agent(ctx, ".."))                          # 应该：没有建成
        print([b.id for b in all_bots(root / "state.db")], sorted(p.name for p in (root / "bots").iterdir()))   # 应该：['bot-1'] ['bot-1', 'main']
        print(take_newcomers(), take_newcomers())               # 应该：['bot-1'] []，取走一次就清空
