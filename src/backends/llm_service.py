# Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.

from abc import ABC, abstractmethod


class LLMService(ABC):
    @abstractmethod
    def get_general_answer(self, question: str) -> str:
        pass

    @abstractmethod
    def get_shell_answer(self, question: str) -> str:
        pass
