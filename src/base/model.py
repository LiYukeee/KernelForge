import os

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model


load_dotenv()


def _nonnegative_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default
    value = int(raw_value)
    if value < 0:
        raise ValueError(f"{name} must be a non-negative integer.")
    return value


def _positive_float_env(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default
    value = float(raw_value)
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero.")
    return value


def _optional_positive_int_env(name: str) -> int | None:
    """读取可选的正整数环境变量；未设置或为空时返回 None。"""
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return None
    value = int(raw_value)
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer.")
    return value


def load_model(*, streaming: bool = False):
    """创建项目共用的 DeepSeek 协议聊天模型。"""
    return init_chat_model(
        model=os.getenv("MODEL_NAME"),
        model_provider=os.getenv("MODEL_PROVIDER") or "deepseek",
        base_url=os.getenv("BASE_URL"),
        api_key=os.getenv("API_KEY"),
        streaming=streaming,
        stream_usage=streaming,
        max_retries=_nonnegative_int_env("MODEL_MAX_RETRIES", 2),
        timeout=_positive_float_env("MODEL_TIMEOUT_SECONDS", 180.0),
        max_tokens=_optional_positive_int_env("MODEL_MAX_TOKENS"),
    )
