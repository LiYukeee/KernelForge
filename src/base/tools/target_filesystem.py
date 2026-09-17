"""PLAN、CODE 和 LOG Agent 共用的 TARGET 文件访问策略。"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Mapping

from deepagents.backends import FilesystemBackend
from deepagents.backends.protocol import (
    EditResult,
    GlobResult,
    GrepResult,
    LsResult,
    ReadResult,
    WriteResult,
)
from deepagents.middleware import FilesystemMiddleware, FilesystemPermission


AgentRole = str

_SRC_ROOT = Path(__file__).resolve().parents[2]
_POLICY_FILE_NAME = "filesystem.json"
_ROLE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")

TARGET_FILESYSTEM_TOOL_NAMES = [
    "ls",
    "read_file",
    "write_file",
    "edit_file",
    "glob",
    "grep",
]

# deepagents 中间件在驱逐超长工具结果 / 超长 HumanMessage 时写入的内部目录。
# 这些路径必须对读写同时放行，否则驱逐写入会静默失败（保留原消息）。
_EVICTION_INTERNAL_PATHS = (
    "/large_tool_results",
    "/large_tool_results/**",
    "/conversation_history",
    "/conversation_history/**",
)

# deepagents 以 4 字符 ≈ 1 token 的比例估算文本长度。
_CHARS_PER_TOKEN = 4
_DEFAULT_CONTEXT_WINDOW_TOKENS = 180_220
# 为系统提示、工具定义与回复预留的 token 余量。
_RESERVED_TOKENS = 32_768


def context_window_tokens() -> int:
    """读取 MODEL_CONTEXT_WINDOW；未设置、为空或非法时回退到默认值。"""
    raw_value = os.getenv("MODEL_CONTEXT_WINDOW")
    if raw_value is None or not raw_value.strip():
        return _DEFAULT_CONTEXT_WINDOW_TOKENS
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(
            f"MODEL_CONTEXT_WINDOW must be a positive integer, got: {raw_value!r}"
        ) from exc
    if value <= 0:
        raise ValueError(
            f"MODEL_CONTEXT_WINDOW must be a positive integer, got: {raw_value!r}"
        )
    return value


def eviction_limits_from_context_window() -> tuple[int, int]:
    """根据模型上下文窗口推导 (tool, human) 驱逐阈值（token）。

    设定原则：单个工具结果与单条 HumanMessage 都不应占用超过上下文的一小半，
    这样即便叠加系统提示、历史消息与最大输出，也不会突破模型输入上限。
    预留余量不会超过上下文窗口的 1/4，避免小窗口配置下阈值退化为 1。
    """
    context_window = context_window_tokens()
    reserved = min(_RESERVED_TOKENS, context_window // 4)
    budget = max(context_window - reserved, 1)
    tool_limit = max(budget // 2, 1)
    human_limit = max(budget // 2, 1)
    return tool_limit, human_limit


@dataclass(frozen=True)
class TargetFilesystemPolicy:
    """从 Agent 目录配置加载的虚拟路径白名单。"""

    read_paths: tuple[str, ...]
    write_paths: tuple[str, ...]


def _with_eviction_paths(paths: tuple[str, ...]) -> tuple[str, ...]:
    """附加 deepagents 驱逐机制使用的内部目录，保持去重与顺序稳定。"""
    merged = list(paths)
    for internal_path in _EVICTION_INTERNAL_PATHS:
        if internal_path not in merged:
            merged.append(internal_path)
    return tuple(merged)


def _render_policy_path(path: str, *, round_number: int, config_path: Path) -> str:
    """渲染并校验一个精确路径或 ``/**`` 子树规则。"""
    rendered = path.replace("{round_number}", str(round_number))
    if "{" in rendered or "}" in rendered:
        raise ValueError(f"文件系统配置包含未知占位符：{config_path}: {path!r}")
    if not rendered.startswith("/") or "\\" in rendered:
        raise ValueError(
            f"文件系统配置路径必须是 POSIX 绝对路径：{config_path}: {path!r}"
        )

    subtree = rendered.endswith("/**")
    if rendered == "/**":
        base_path = "/"
    elif subtree:
        base_path = rendered[:-3]
    else:
        base_path = rendered
    if any(character in base_path for character in "*?[]"):
        raise ValueError(
            f"文件系统配置只支持精确路径和 /** 规则：{config_path}: {path!r}"
        )

    normalized = PurePosixPath(base_path)
    if ".." in normalized.parts or "~" in normalized.parts:
        raise ValueError(f"文件系统配置路径不能包含 .. 或 ~：{config_path}: {path!r}")
    normalized_text = normalized.as_posix()
    if not normalized_text.startswith("/") or normalized_text != base_path:
        raise ValueError(f"文件系统配置路径必须是规范路径：{config_path}: {path!r}")
    if subtree:
        return "/**" if normalized_text == "/" else f"{normalized_text}/**"
    return normalized_text


def load_target_filesystem_policy(
    *,
    role: AgentRole,
    round_number: int,
) -> TargetFilesystemPolicy:
    """加载 ``src/<role>/filesystem.json`` 并渲染当前轮次。"""
    if round_number <= 0:
        raise ValueError("round_number 必须大于 0。")
    if not _ROLE_PATTERN.fullmatch(role):
        raise ValueError(f"Agent 角色名只能包含小写字母、数字和下划线：{role!r}")

    config_path = _SRC_ROOT / role / _POLICY_FILE_NAME
    if not config_path.is_file():
        raise FileNotFoundError(f"Agent 缺少文件系统配置：{config_path}")
    try:
        raw_config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Agent 文件系统配置不是合法 JSON：{config_path}: {exc}") from exc

    if not isinstance(raw_config, dict) or set(raw_config) != {"read", "write"}:
        raise ValueError(f"Agent 文件系统配置必须且只能包含 read、write：{config_path}")

    rendered_paths: dict[str, tuple[str, ...]] = {}
    for operation in ("read", "write"):
        paths = raw_config[operation]
        if not isinstance(paths, list) or any(
            not isinstance(path, str) for path in paths
        ):
            raise ValueError(
                f"Agent 文件系统配置的 {operation} 必须是字符串数组：{config_path}"
            )
        rendered = tuple(
            _render_policy_path(
                path,
                round_number=round_number,
                config_path=config_path,
            )
            for path in paths
        )
        if len(rendered) != len(set(rendered)):
            raise ValueError(f"Agent 文件系统配置的 {operation} 包含重复路径：{config_path}")
        rendered_paths[operation] = rendered

    return TargetFilesystemPolicy(
        read_paths=_with_eviction_paths(rendered_paths["read"]),
        write_paths=_with_eviction_paths(rendered_paths["write"]),
    )


class TargetFilesystemBackend(FilesystemBackend):
    """在磁盘后端执行最终读写白名单，防止权限 glob 的漏配路径。"""

    def __init__(
        self,
        root_dir: Path,
        *,
        role: AgentRole,
        round_number: int,
        policy: TargetFilesystemPolicy | None = None,
    ) -> None:
        super().__init__(root_dir=root_dir, virtual_mode=True)
        self._policy = policy or load_target_filesystem_policy(
            role=role,
            round_number=round_number,
        )

    @staticmethod
    def _normalize_virtual_path(path: str) -> PurePosixPath | None:
        normalized = path.replace("\\", "/")
        if not normalized.startswith("/"):
            return None
        candidate = PurePosixPath(normalized)
        if ".." in candidate.parts or "~" in candidate.parts:
            return None
        return candidate

    @staticmethod
    def _matches_policy_path(path: PurePosixPath, pattern: str) -> bool:
        if pattern == "/**":
            return True
        if pattern.endswith("/**"):
            root = PurePosixPath(pattern[:-3])
            return path == root or root in path.parents
        return path == PurePosixPath(pattern)

    @classmethod
    def _matches_any_policy_path(
        cls,
        path: PurePosixPath,
        patterns: tuple[str, ...],
    ) -> bool:
        return any(cls._matches_policy_path(path, pattern) for pattern in patterns)

    def _can_read_virtual(self, path: str) -> bool:
        candidate = self._normalize_virtual_path(path)
        if candidate is None:
            return False
        return self._matches_any_policy_path(
            candidate,
            self._policy.read_paths,
        )

    def _can_write_virtual(self, path: str) -> bool:
        candidate = self._normalize_virtual_path(path)
        if candidate is None:
            return False
        return self._matches_any_policy_path(candidate, self._policy.write_paths)

    def _resolved_virtual_path(self, path: str) -> str | None:
        try:
            resolved = self._resolve_path(path)
            relative = resolved.relative_to(self.cwd)
        except (OSError, RuntimeError, ValueError):
            return None
        return "/" if relative == PurePosixPath(".") else f"/{relative.as_posix()}"

    def _can_read(self, path: str) -> bool:
        resolved = self._resolved_virtual_path(path)
        return (
            resolved is not None
            and self._can_read_virtual(path)
            and self._can_read_virtual(resolved)
        )

    def _can_write(self, path: str) -> bool:
        resolved = self._resolved_virtual_path(path)
        return (
            resolved is not None
            and self._can_write_virtual(path)
            and self._can_write_virtual(resolved)
        )

    def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> ReadResult:
        if not self._can_read(file_path):
            return ReadResult(error=f"Error: permission denied for read on {file_path}")
        return super().read(file_path, offset=offset, limit=limit)

    def write(self, file_path: str, content: str) -> WriteResult:
        if not self._can_write(file_path):
            return WriteResult(error=f"Error: permission denied for write on {file_path}")
        return super().write(file_path, content)

    def edit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> EditResult:
        if not self._can_write(file_path):
            return EditResult(error=f"Error: permission denied for write on {file_path}")
        return super().edit(
            file_path,
            old_string,
            new_string,
            replace_all=replace_all,
        )

    def atomic_write_text(self, file_path: str, content: str) -> None:
        """按当前策略原子写入控制器生成的 UTF-8 文本。"""
        if not self._can_write(file_path):
            raise PermissionError(f"permission denied for write on {file_path}")
        destination = self._resolve_path(file_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary_file = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        )
        temporary_path = Path(temporary_file.name)
        try:
            with temporary_file:
                temporary_file.write(content)
            temporary_path.replace(destination)
        finally:
            temporary_path.unlink(missing_ok=True)

    def atomic_copy(self, source_path: str, destination_path: str) -> None:
        """按当前读写策略原子复制控制器管理的文件。"""
        if not self._can_read(source_path):
            raise PermissionError(f"permission denied for read on {source_path}")
        if not self._can_write(destination_path):
            raise PermissionError(f"permission denied for write on {destination_path}")
        source = self._resolve_path(source_path)
        destination = self._resolve_path(destination_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary_file = tempfile.NamedTemporaryFile(
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        )
        temporary_path = Path(temporary_file.name)
        temporary_file.close()
        try:
            shutil.copy2(source, temporary_path)
            temporary_path.replace(destination)
        finally:
            temporary_path.unlink(missing_ok=True)

    def ls(self, path: str) -> LsResult:
        if not self._can_read(path):
            return LsResult(error=f"Error: permission denied for read on {path}")
        result = super().ls(path)
        if result.entries is not None:
            result.entries = [
                entry for entry in result.entries if self._can_read(entry["path"])
            ]
        return result

    def glob(self, pattern: str, path: str | None = None) -> GlobResult:
        search_path = path or "/"
        if not self._can_read(search_path):
            return GlobResult(error=f"Error: permission denied for read on {search_path}")
        result = super().glob(pattern, path)
        if result.matches is not None:
            result.matches = [
                match for match in result.matches if self._can_read(match["path"])
            ]
        return result

    def grep(
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
        *,
        max_count: int | None = None,
        context_lines: int = 0,
    ) -> GrepResult:
        search_path = path or "/"
        if not self._can_read(search_path):
            return GrepResult(error=f"Error: permission denied for read on {search_path}")
        result = super().grep(
            pattern,
            path,
            glob,
            max_count=max_count,
            context_lines=context_lines,
        )
        if result.matches is not None:
            result.matches = [
                match for match in result.matches if self._can_read(match["path"])
            ]
        return result


@dataclass(frozen=True)
class TargetFilesystemAccess:
    """绑定到单个 TARGET 的后端、中间件和权限规则。"""

    backend: TargetFilesystemBackend
    middleware: FilesystemMiddleware
    permissions: tuple[FilesystemPermission, ...]


def build_target_permissions(
    *,
    role: AgentRole,
    round_number: int,
) -> list[FilesystemPermission]:
    """从 Agent 配置构造权限；规则按 first-match-wins 顺序排列。"""
    policy = load_target_filesystem_policy(
        role=role,
        round_number=round_number,
    )
    return _build_permissions_from_policy(policy)


def _build_permissions_from_policy(
    policy: TargetFilesystemPolicy,
) -> list[FilesystemPermission]:
    """把已校验策略转换为 FilesystemMiddleware 权限。"""

    return [
        FilesystemPermission(
            operations=["read"],
            paths=list(policy.read_paths),
            mode="allow",
        ),
        FilesystemPermission(
            operations=["read"],
            paths=["/**"],
            mode="deny",
        ),
        FilesystemPermission(
            operations=["write"],
            paths=list(policy.write_paths),
            mode="allow",
        ),
        FilesystemPermission(
            operations=["write"],
            paths=["/**"],
            mode="deny",
        ),
    ]


def build_target_filesystem(
    target_path: Path,
    *,
    role: AgentRole,
    round_number: int,
    custom_tool_descriptions: Mapping[str, str] | None = None,
) -> TargetFilesystemAccess:
    """创建以 TARGET 为虚拟根目录的受限文件工具中间件。"""
    policy = load_target_filesystem_policy(
        role=role,
        round_number=round_number,
    )
    permissions = _build_permissions_from_policy(policy)
    backend = TargetFilesystemBackend(
        target_path,
        role=role,
        round_number=round_number,
        policy=policy,
    )
    # 依据 MODEL_CONTEXT_WINDOW（未设置时用模型默认值）推导驱逐阈值，
    # 防止超长工具结果或用户消息把上下文撑爆。
    tool_limit, human_limit = eviction_limits_from_context_window()
    middleware = FilesystemMiddleware(
        backend=backend,
        tools=TARGET_FILESYSTEM_TOOL_NAMES,
        custom_tool_descriptions=custom_tool_descriptions,
        tool_token_limit_before_evict=tool_limit,
        human_message_token_limit_before_evict=human_limit,
        # DeepAgents 0.7.x 只在 create_deep_agent 上公开 permissions；普通
        # create_agent 需要通过中间件参数接入，因此把私有兼容点集中在这里。
        _permissions=permissions,
    )
    return TargetFilesystemAccess(
        backend=backend,
        middleware=middleware,
        permissions=tuple(permissions),
    )
