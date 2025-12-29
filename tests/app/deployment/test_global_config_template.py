"""测试部署完成后生成的全局配置模板内容。"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from app.deployment.models import DeploymentConfig, LLMConfig
from app.deployment.service import DeploymentService
from config.model import ConfigModel

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_global_config_template_writes_default_llm_id(temp_config_env: dict[str, Path]) -> None:
    """部署生成的全局模板应写入默认 Chat 模型 llm_id。"""
    user_path = temp_config_env["user_path"]
    global_path = temp_config_env["global_path"]

    # 构造一个 root 用户的现有配置（模拟部署过程中已生成/写入的其它字段）
    base = ConfigModel().to_dict()
    base["witty"]["api_key"] = "SHOULD_BE_CLEARED"
    base["witty"]["default_app"] = "agent-app-id"
    base["witty"]["llm_chat"] = ""  # 未配置
    user_path.write_text(json.dumps(base), encoding="utf-8")

    svc = DeploymentService()

    deployment_config = DeploymentConfig(
        llm=LLMConfig(
            endpoint="http://127.0.0.1:9000/v1",
            api_key="deploy-api-key",
            model="deploy-llm-id",
        ),
    )

    await svc._create_global_config_template(deployment_config)  # noqa: SLF001

    assert global_path.exists()
    template = json.loads(global_path.read_text(encoding="utf-8"))

    # token 不应传播给其他用户
    assert template["witty"]["api_key"] == ""

    # 默认 llm_id 应被写入
    assert template["witty"]["llm_chat"] == "deploy-llm-id"
