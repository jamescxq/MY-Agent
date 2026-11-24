from .basic import TASKS as BASIC_TASKS
from .bots import TASKS as BOTS_TASKS
from .guests import TASKS as GUESTS_TASKS
from .greeting import TASKS as GREETING_TASKS
from .schedule import TASKS as SCHEDULE_TASKS

# 所有题目。以后每多一种能力，就多一个文件，在这里加一行
ALL_TASKS = BASIC_TASKS + BOTS_TASKS + GUESTS_TASKS + GREETING_TASKS + SCHEDULE_TASKS
