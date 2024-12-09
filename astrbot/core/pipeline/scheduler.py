from . import STAGES_ORDER
from .stage import registered_stages, Stage
from .context import PipelineContext
from typing import AsyncGenerator
from astrbot.core.platform import AstrMessageEvent
from astrbot.core.message.message_event_result import MessageEventResult, EventResultType
from astrbot.core import logger

class PipelineScheduler():
    def __init__(self, context: PipelineContext):
        registered_stages.sort(key=lambda x: STAGES_ORDER.index(x.__class__ .__name__))
        self.ctx = context
        
    async def initialize(self):
        for stage in registered_stages:
            logger.debug(f"初始化阶段 {stage.__class__ .__name__}")
            
            await stage.initialize(self.ctx)
            
    async def _process_stages(self, event: AstrMessageEvent, from_stage=0):
        for i in range(from_stage, len(registered_stages)):
            stage = registered_stages[i]
            logger.debug(f"执行阶段 {stage.__class__ .__name__}")
            coro = stage.process(event)
            if isinstance(coro, AsyncGenerator):
                async for _ in coro:
                    if event.is_stopped():
                        logger.debug(f"阶段 {stage.__class__ .__name__} 已终止事件传播。")
                        break
                    await self._process_stages(event, i + 1)
            else:
                await coro

                if event.is_stopped():
                    logger.debug(f"阶段 {stage.__class__ .__name__} 已终止事件传播。")
                    break

            if event.is_stopped():
                logger.debug(f"阶段 {stage.__class__ .__name__} 已终止事件传播。")
                break
    
    async def execute(self, event: AstrMessageEvent):
        '''执行 pipeline'''
        await self._process_stages(event)