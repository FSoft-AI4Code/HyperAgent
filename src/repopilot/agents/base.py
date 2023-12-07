from abc import abstractmethod
from typing import Any

from langchain.callbacks.manager import Callbacks
from langchain.chains.base import Chain

from langchain_experimental.plan_and_execute.schema import StepResponse
from langchain_experimental.pydantic_v1 import BaseModel
from langchain_experimental.plan_and_execute.executors.base import BaseExecutor

class ChainExecutor(BaseExecutor):
    """Chain executor."""

    chain: Chain
    """The chain to use."""

    def step(
        self, inputs: dict, callbacks: Callbacks = None, **kwargs: Any
    ) -> StepResponse:
        """Take step."""
        response = self.chain(inputs, callbacks=callbacks)
        if "intermediate_steps" in response:
            return StepResponse(response=response["output"]), response["intermediate_steps"]
        else:
            return StepResponse(response=response["output"])

    async def astep(
        self, inputs: dict, callbacks: Callbacks = None, **kwargs: Any
    ) -> StepResponse:
        """Take step."""
        response = await self.chain.arun(**inputs, callbacks=callbacks)
        return StepResponse(response=response)