# 每天用量上限：今天发出去和收回来的 token 加起来到了上限，就不再调模型。
# 防的是"不知不觉花掉很多"：比如循环出了毛病停不下来，或者一晚上到点的提醒特别多。
#
# 上限写在 .env 的 DAILY_TOKEN_LIMIT（见 config.py），写 0 表示不限。
# 用了多少，是把 trace.jsonl 里今天的那些行加起来（用 usage.py 的 read_rows），所以不用另外存一份数。
# 每调一次模型之前都要读一遍这个文件；文件只有几十到几百 KB，比调一次模型快得多。
#
# 注意两点：
#   1. 数的是 token 的个数，不是钱。开了提示词缓存以后，从缓存读的那部分其实便宜很多，
#      但这里照样按个数算，所以这个上限是偏严的。它是刹车，不是账单。
#   2. 评测不受它管（evals/run.py 里关掉了）：评测是人手动跑的，用量记在评测自己的报告里。
from datetime import date
import config
from config import LOGS
from .usage import read_rows


class OverLimit(Exception):
    """今天的用量到上限了。里面的文字是给用户看的。"""


def used_today(folder=LOGS):
    """今天一共用了多少 token（发的加上回的）。"""
    rows = read_rows(folder, day=date.today().isoformat())
    return sum(row["input_tokens"] + row["output_tokens"] for row in rows)


def check_limit(folder=LOGS):
    """调模型之前先过这一关：到上限了就抛出 OverLimit，没到就什么都不做。"""
    limit = config.DAILY_TOKEN_LIMIT
    if limit <= 0:
        return
    used = used_today(folder)
    if used >= limit:
        raise OverLimit(
            f"今天的用量到上限了（已用 {used} 个 token，上限 {limit}），我先停下，明天自动恢复。"
            "想现在继续：把 .env 里的 DAILY_TOKEN_LIMIT 调大，再重启程序。"
        )


if __name__ == "__main__":
    import tempfile
    from pathlib import Path
    from .trace import write_trace

    with tempfile.TemporaryDirectory() as tmp:          # 临时文件夹，假数字不进真的记录
        folder = Path(tmp)
        config.DAILY_TOKEN_LIMIT = 10000
        print(used_today(folder))                       # 应该：0
        check_limit(folder)                             # 应该：什么都不发生
        write_trace("main", 1, 6000, 100, 1.0, folder=folder)
        check_limit(folder)                             # 应该：还是什么都不发生（6100 没到 10000）
        write_trace("main", 2, 6000, 100, 1.0, folder=folder)
        print(used_today(folder))                       # 应该：12200
        try:
            check_limit(folder)
        except OverLimit as exc:
            print(exc)                                  # 应该：今天的用量到上限了……
        config.DAILY_TOKEN_LIMIT = 0
        check_limit(folder)                             # 应该：什么都不发生（0 表示不限）
