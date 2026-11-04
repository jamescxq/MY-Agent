from agents.prompt.builder import build_system_prompt
from agents.loop import run_agent
from agents.tools import TOOLS

messages = []
system_prompt = build_system_prompt()

while True:
    user_input = input("你：")
    messages.append({"role": "user", "content": user_input})

    reply = run_agent(system_prompt, TOOLS, messages)
    # 名字叫什么你可以自己改
    print("小牛", reply)

