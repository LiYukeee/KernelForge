"""PLAN 和 CODE Agent 共用的 TARGET 文件访问策略。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal, Mapping

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


AgentRole = Literal["plan", "code"]

TARGET_FILESYSTEM_TOOL_NAMES = [
    "ls",
    "read_file",
    "write_file",
    "edit_file",
    "glob",
    "grep",
]

_READABLE_PATHS = [
    "/",
    "/model.py",
    "/model_new.py",
    "/exp",
    "/exp/**",
    "/bench_output",
    "/bench_output/**",
]


class TargetFilesystemBackend(FilesystemBackend):
    """在磁盘后端执行最终读写白名单，防止权限 glob 的漏配路径。"""

    def __init__(
        self,
        root_dir: Path,
        *,
        role: AgentRole,
        round_number: int,
    ) -> None:
        super().__init__(root_dir=root_dir, virtual_mode=True)
        self._role = role
        self._round_path = PurePosixPath(f"/exp/round_{round_number}")

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
    def _is_at_or_below(path: PurePosixPath, root: PurePosixPath) -> bool:
        return path == root or root in path.parents

    def _can_read_virtual(self, path: str) -> bool:
        candidate = self._normalize_virtual_path(path)
        if candidate is None:
            return False
        if candidate in {
            PurePosixPath("/"),
            PurePosixPath("/model.py"),
            PurePosixPath("/model_new.py"),
        }:
            return True
        return self._is_at_or_below(
            candidate,
            PurePosixPath("/exp"),
        ) or self._is_at_or_below(
            candidate,
            PurePosixPath("/bench_output"),
        )

    def _can_write_virtual(self, path: str) -> bool:
        candidate = self._normalize_virtual_path(path)
        if candidate is None:
            return False
        if self._role == "code" and candidate == PurePosixPath("/model_new.py"):
            return True
        return self._is_at_or_below(candidate, self._round_path)

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
    """构造角色权限；规则按 first-match-wins 顺序排列。"""
    if role not in {"plan", "code"}:
        raise ValueError(f"不支持的 Agent 角色：{role!r}")
    if round_number <= 0:
        raise ValueError("round_number 必须大于 0。")

    round_path = f"/exp/round_{round_number}"
    writable_paths = [round_path, f"{round_path}/**"]
    if role == "code":
        writable_paths.insert(0, "/model_new.py")

    return [
        FilesystemPermission(
            operations=["read"],
            paths=list(_READABLE_PATHS),
            mode="allow",
        ),
        FilesystemPermission(
            operations=["read"],
            paths=["/**"],
            mode="deny",
        ),
        FilesystemPermission(
            operations=["write"],
            paths=writable_paths,
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
    permissions = build_target_permissions(
        role=role,
        round_number=round_number,
    )
    backend = TargetFilesystemBackend(
        target_path,
        role=role,
        round_number=round_number,
    )
    middleware = FilesystemMiddleware(
        backend=backend,
        tools=TARGET_FILESYSTEM_TOOL_NAMES,
        custom_tool_descriptions=custom_tool_descriptions,
        tool_token_limit_before_evict=None,
        human_message_token_limit_before_evict=None,
        # DeepAgents 0.7.x 只在 create_deep_agent 上公开 permissions；普通
        # create_agent 需要通过中间件参数接入，因此把私有兼容点集中在这里。
        _permissions=permissions,
    )
    return TargetFilesystemAccess(
        backend=backend,
        middleware=middleware,
        permissions=tuple(permissions),
    )
