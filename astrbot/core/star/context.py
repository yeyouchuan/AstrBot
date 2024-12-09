import heapq
from asyncio import Queue
from . import StarMetadata
from typing import List, Dict, TypedDict, Union

from astrbot.core.platform import Platform
from astrbot.core.provider import Provider
from astrbot.core.db import BaseDatabase
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.provider.tool import FuncCall
from astrbot.core.platform.astr_message_event import MessageSesion
from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.provider.manager import ProviderManager
from astrbot.core.platform.manager import PlatformManager
from .star import star_registry, star_map, StarMetadata
from .star_handler import star_handlers_registry, star_handlers_map, StarHandlerMetadata
from .filter.command import CommandFilter
from .filter.regex import RegexFilter
from typing import Awaitable

class StarCommand(TypedDict):
    full_command_name: str
    command_name: str

class Context:
    '''
    暴露给插件的接口上下文。
    '''
    _event_queue: Queue = None
    '''事件队列。消息平台通过事件队列传递消息事件。'''
    
    _config: AstrBotConfig = None
    '''AstrBot 配置信息'''
    
    _db: BaseDatabase = None
    '''AstrBot 数据库'''
    
    provider_manager: ProviderManager = None
    
    platform_manager: PlatformManager = None

    def __init__(self, event_queue: Queue, config: AstrBotConfig, db: BaseDatabase):
        self._event_queue = event_queue
        self._config = config
        self._db = db

    def get_registered_star(self, star_name: str) -> StarMetadata:
        return star_map.get(star_name, None)
    
    def get_all_stars(self) -> List[StarMetadata]:
        return star_registry
    
    def get_llm_tools(self) -> FuncCall:
        '''
        获取 LLM Tools。
        '''
        return self.provider_manager.llm_tools
    
    
    # def get_star_commands(self, star_name: str) -> List[]:
    #     '''获得一个'''
        
    # def register_llm_tool(self, name: str, func_args: list, desc: str, func_obj: Awaitable) -> None:
    #     '''
    #     为函数调用（function-calling / tools-use）添加工具。
        
    #     @param name: 函数名
    #     @param func_args: 函数参数列表，格式为 [{"type": "string", "name": "arg_name", "description": "arg_description"}, ...]
    #     @param desc: 函数描述
    #     @param func_obj: 异步处理函数。
        
    #     异步处理函数会接收到额外的的关键词参数：event: AstrMessageEvent, context: Context。
    #     '''
    #     self.llm_tools.add_func(name, func_args, desc, func_obj)
    
    # def unregister_llm_tool(self, name: str) -> None:
    #     '''
    #     删除一个函数调用工具。
    #     '''
    #     self.llm_tools.remove_func(name)
    
    def register_commands(self, star_name: str, command_name: str, desc: str, priority: int, awaitable: Awaitable, use_regex=False, ignore_prefix=False):
        '''
        注册一个命令。
        
        [Deprecated] 推荐使用装饰器注册指令。该方法将在未来的版本中被移除。
        
        @param star_name: 插件（Star）名称。
        @param command_name: 命令名称。
        @param desc: 命令描述。
        @param priority: 优先级。1-10。
        @param awaitable: 异步处理函数。
        
        '''
        md = StarHandlerMetadata(
            handler_full_name=awaitable.__module__ + "_" + awaitable.__name__,
            handler_name=awaitable.__name__,
            handler_module_str=awaitable.__module__,
            handler=awaitable,
            event_filters=[],
            desc=desc
        )
        if use_regex:
            md.event_filters.append(RegexFilter(
                regex=command_name
            ))
        else:
            md.event_filters.append(CommandFilter(
                command_name=command_name,
                handler_md=md
            ))
        star_handlers_registry.append(md)
    
    def register_provider(self, provider: Provider):
        '''
        注册一个 LLM Provider。
        '''
        self.provider_manager.provider_insts.append(provider)
    
    def get_all_providers(self) -> List[Provider]:
        '''
        获取所有 LLM Provider。
        '''
        return self.provider_manager.provider_insts
    
    def get_using_provider(self) -> Provider:
        '''
        获取当前使用的 LLM Provider。
        
        通过 /provider 指令切换。
        '''
        return self.provider_manager.curr_provider_inst
    
    def get_config(self) -> AstrBotConfig:
        '''
        获取 AstrBot 配置信息。
        '''
        return self._config
    
    def get_db(self) -> BaseDatabase:
        '''
        获取 AstrBot 数据库。
        '''
        return self._db
    
    def get_event_queue(self) -> Queue:
        '''
        获取事件队列。
        '''
        return self._event_queue
    
    async def send_message(self, session: Union[str, MessageSesion], message_chain: MessageChain) -> bool:
        '''
        根据 session(unified_msg_origin) 发送消息。
        
        @param session: 消息会话。通过 event.session 或者 event.unified_msg_origin 获取。
        @param message_chain: 消息链。
        
        @return: 是否找到匹配的平台。
        
        当 session 为字符串时，会尝试解析为 MessageSesion 对象，如果解析失败，会抛出 ValueError 异常。
        '''
        
        if isinstance(session, str):
            try:
                session = MessageSesion.from_str(session)
            except BaseException as e:
                raise ValueError("不合法的 session 字符串: " + str(e))

        for platform in self.registered_platforms:
            if platform.meta().name == session.platform_name:
                await platform.send_by_session(session, message_chain)
                return True
        return False
