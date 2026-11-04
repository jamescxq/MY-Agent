from .get_time import GET_TIME_TOOL, get_time
from .read_file import READ_FILE_TOOL, read_file
from .list_file import LIST_FILE_TOOL, list_file
from .edit_file import EDIT_FILE_TOOL, edit_file
from .write_file import WRITE_FILE_TOOL,write_file

REGISTRY = [
    (GET_TIME_TOOL, get_time),
    (READ_FILE_TOOL, read_file),
    (LIST_FILE_TOOL, list_file),
    (EDIT_FILE_TOOL, edit_file),
    (WRITE_FILE_TOOL,write_file),
]

TOOLS = [schema for schema, func in REGISTRY]
TOOL_FUNCTIONS = {schema["name"]: func for schema, func in REGISTRY}

if __name__ == "__main__":
    print(TOOL_FUNCTIONS)
