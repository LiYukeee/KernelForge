"""CODE Agent 的 TARGET 文件工具配置。"""

from __future__ import annotations

from deepagents.backends import FilesystemBackend
from deepagents.middleware import FilesystemMiddleware


CODE_FILESYSTEM_TOOL_NAMES = ["ls", "read_file", "edit_file", "glob", "grep"]

_VIRTUAL_PATH_RULE = (
    "路径位于 TARGET 的虚拟文件系统中：`/` 表示 TARGET 根目录。路径参数必须"
    "使用虚拟绝对路径；不要传入 `/home/...` 形式的宿主机路径，也不要使用 `..` "
    "或 `~`。"
)

CODE_FILESYSTEM_TOOL_DESCRIPTIONS = {
    "ls": (
        "列出 TARGET 目录中的直接子项，用于了解文件布局。"
        f"{_VIRTUAL_PATH_RULE} `path` 示例：`/`、`/exp/round_1`。"
    ),
    "read_file": (
        "读取 TARGET 中的文件。大文件应通过 `offset` 和 `limit` 分页读取；编辑前"
        "必须先读取相关代码。"
        f"{_VIRTUAL_PATH_RULE} `file_path` 示例：`/model.py`、"
        "`/exp/round_1/plan.md`。"
    ),
    "edit_file": (
        "对 TARGET 中已经读取过的文件执行精确字符串替换。`old_string` 必须与源文"
        "本完全一致且默认只能匹配一次；不要包含读取结果中的行号。"
        f"{_VIRTUAL_PATH_RULE} 通常只应编辑 `/model_new.py` 或计划明确允许的文件。"
    ),
    "glob": (
        "在 TARGET 中查找匹配 glob 的文件。`path` 是可选的搜索起点，必须遵守虚拟"
        "路径规则；`pattern` 是 glob 表达式，可使用 `*`、`**` 和 `?`。"
        f"{_VIRTUAL_PATH_RULE}"
    ),
    "grep": (
        "在 TARGET 文件内容中搜索字面量文本，不支持正则表达式。`path` 是可选的"
        "搜索起点，`glob` 可限制文件类型。"
        f"{_VIRTUAL_PATH_RULE}"
    ),
}


def build_code_filesystem_middleware(
    backend: FilesystemBackend,
) -> FilesystemMiddleware:
    """创建绑定到 TARGET 磁盘后端的受限文件工具中间件。"""
    return FilesystemMiddleware(
        backend=backend,
        tools=CODE_FILESYSTEM_TOOL_NAMES,
        custom_tool_descriptions=CODE_FILESYSTEM_TOOL_DESCRIPTIONS,
    )
