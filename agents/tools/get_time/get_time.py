from datetime import datetime

GET_TIME_TOOL = {
    "name": "get_time",
    "description": "获取当前的日期和时间。用户问现在几点、今天几号、星期几，或者需要知道当前时间时调用。",
    "input_schema": {
        "type": "object",
        "properties": {},
    },
}

# 这个工具用不到 ctx，但每个工具的第一个参数都统一是它
def get_time(ctx):
    now = datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S %A")