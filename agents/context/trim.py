

MAX_CHARS = 50000
TARGET_CHARS = 35000

def strip_thinking(messages):
    for message in messages:
        if message["role"] != "assistant" or isinstance(message["content"], str):
            continue
        kept = [block for block in message["content"]
                if block.type not in ("thinking", "redacted_thinking")]
        message["content"] = kept or "(这一轮没有文字回复)"

def count_chars(messages):
    return sum(len(str(message))for message in messages)

def trim_messages(messages):
    if count_chars(messages) <=MAX_CHARS:
        return messages
    starts = [i for i, message in enumerate(messages)
              if message["role"] == "user" and isinstance(message["content"], str)]
    for start in starts[1:]:
        kept = messages[start:]
        if count_chars(kept) <= TARGET_CHARS or start == starts[-1] :
            strip_thinking(kept)
            print(f"【系统】对话太长，已去掉旧内容：{len(messages)} 条 → {len(kept)} 条")
            return kept
    return messages