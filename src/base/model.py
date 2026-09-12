import os

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model


load_dotenv()


def load_model(*, streaming: bool = False):
    """创建项目共用的 DeepSeek 协议聊天模型。"""
    return init_chat_model(
        model=os.getenv("MODEL_NAME"),
        model_provider=os.getenv("MODEL_PROVIDER") or "deepseek",
        base_url=os.getenv("BASE_URL"),
        api_key=os.getenv("API_KEY"),
        streaming=streaming,
        stream_usage=streaming,
    )
