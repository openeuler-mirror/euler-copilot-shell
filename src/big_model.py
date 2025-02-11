"""大模型客户端"""

import re
from collections.abc import AsyncGenerator

from openai import AsyncOpenAI


def validate_url(url: str) -> bool:
    """校验 URL 是否合法

    校验 URL 是否以 http:// 或 https:// 开头。
    """
    return re.match(r"^https?://", url) is not None


class OpenAIClient:
    """大模型客户端"""

    def __init__(self, base_url: str, model: str, api_key: str = "") -> None:
        """初始化大模型客户端"""
        if not validate_url(base_url):
            msg = "无效的 API URL，请确保 URL 以 http:// 或 https:// 开头。"
            raise ValueError(msg)
        self.model = model
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    async def generate_command_suggestion(self, prompt: str) -> AsyncGenerator[str, None]:
        """生成命令建议

        异步调用 OpenAI 或兼容接口的大模型生成命令建议，支持流式输出。
        请确保已安装 openai 库（pip install openai）。
        """
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
        )
        async for chunk in response:
            content = chunk.choices[0].delta.content
            if content:
                yield content

    async def get_available_models(self) -> list[str]:
        """获取当前 LLM 服务中可用的模型，返回名称列表

        调用 LLM 服务的模型列表接口，并解析返回结果提取模型名称。
        """
        models_response = await self.client.models.list()
        return [model.id async for model in models_response]
