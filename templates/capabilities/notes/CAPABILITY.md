---
name: 笔记与记忆
description: 读、写、改你自己文件夹里的文件；把用户告诉你的事记下来
tools: read_file, list_file, edit_file, write_file
status: 可用
always: 是
---

# 笔记与记忆

每个 Agent 都有这个能力，不能关：没有它，Agent 连自己的记忆都写不了。

## 风险规则

- 覆盖已有的文件、替换文件里的内容，要用户同意（代码在 `agents/permission/gate.py`）。
- 新建文件、在文件末尾追加，不用问。
