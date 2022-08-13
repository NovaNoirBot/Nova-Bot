from collections import defaultdict
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING, Optional, List, Type, Any, Callable, Dict, Union, NoReturn, TypeVar, Iterator

from nonebot import on_command
from nonebot.adapters.onebot.v11 import GROUP_ADMIN, GROUP_OWNER, GroupMessageEvent
from nonebot.adapters.onebot.v11 import Message as OneBotMessage, Bot as OneBotBot, Event as OneBotEvent
from nonebot.dependencies import Dependent
from nonebot.exception import IgnoredException
from nonebot.internal.adapter import Message, MessageSegment, MessageTemplate, Bot, Event
from nonebot.log import logger
from nonebot.matcher import Matcher
from nonebot.message import run_preprocessor
from nonebot.params import CommandArg, Arg
from nonebot.permission import SUPERUSER
from nonebot.typing import T_Handler, T_DependencyCache, T_State, T_TypeUpdater, T_PermissionUpdater

from novabot.core.service.config_manager import ServiceConfig
from novabot.core.service.scheduler import scheduler_services, SchedulerServiceMeta

T = TypeVar("T")

services: List[Type["Service"]] = []
services_dict: Dict[int, Type["Service"]] = defaultdict()

enable_ = on_command(".开启",
                     aliases={".打开", ".enable"},
                     permission=SUPERUSER | GROUP_OWNER | GROUP_ADMIN,
                     block=True,
                     priority=1)
disable_ = on_command(".禁用",
                      aliases={".关闭", ".disable"},
                      permission=SUPERUSER | GROUP_OWNER | GROUP_ADMIN,
                      block=True,
                      priority=1)


class ServiceMeta(type):
    if TYPE_CHECKING:
        service_name: Optional[str]
        help_: Optional[str]
        matcher: Type["Matcher"]
        cd: int
        limit: int
        enable_on_default: bool
        invisible: bool

    def __repr__(self) -> str:
        return (
            f"<Service of {self.service_name or self.matcher.plugin_name or 'unknown'}, "
            f"cd={self.cd}, "
            f"limit={self.limit}, enable_on_default={self.enable_on_default}, "
            f"invisible={self.invisible}>"
        )

    def __str__(self) -> str:
        return repr(self)


class Service(metaclass=ServiceMeta):
    """"""
    service_name: str = None

    help_: Optional[str] = None

    matcher: Type["Matcher"] = Matcher

    cd: int = 0

    limit: int = 0

    enable_on_default: bool = True

    invisible: bool = False

    def __init__(self):
        ...

    def __repr__(self) -> str:
        return (
            f"<Service of {self.service_name or self.matcher.plugin_name or 'unknown'}, "
            f"cd={self.cd}, "
            f"limit={self.limit}, enable_on_default={self.enable_on_default}, "
            f"invisible={self.invisible}>"
        )

    def __str__(self) -> str:
        return repr(self)

    @classmethod
    def new(cls,
            service_name: str,  # Due to the reason that we cannot get a unique and stable name from the matcher,
            # there's a must to set the service_name to be identified,
            # otherwise we need to change the code of nb2.
            matcher: Optional[Type["Matcher"]] = Matcher,
            *,
            help_: Optional[str] = "",
            cd: Optional[int] = 0,  # To-Do: Change the cd and limit into readable format like `seconds=10`
            limit: Optional[int] = 0,
            enable_on_default: Optional[bool] = True,
            invisible: Optional[bool] = False
            ):
        """
        创建一个新的事件响应器，并存储至 `matchers <#matchers>`_

        参数:
            type_: 事件响应器类型，与 `event.get_type()` 一致时触发，空字符串表示任意
            rule: 匹配规则
            permission: 权限
            handlers: 事件处理函数列表
            temp: 是否为临时事件响应器，即触发一次后删除
            priority: 响应优先级
            block: 是否阻止事件向更低优先级的响应器传播
            plugin: 事件响应器所在插件
            module: 事件响应器所在模块
            default_state: 默认状态 `state`
            expire_time: 事件响应器最终有效时间点，过时即被删除

        返回:
            Type[Matcher]: 新的事件响应器类
        """
        NewService = type(
            "Service",
            (Service,),
            {
                "matcher": matcher,
                "service_name": service_name,
                "help_": help_,
                "cd": cd,
                "limit": limit,
                "enable_on_default": enable_on_default,
                "invisible": invisible
                # To-Do: Read Enabled/Disabled Groups and So On Here.
            }
        )
        logger.trace(f"Define new service {NewService}")

        services.append(NewService)
        services_dict[id(matcher)] = NewService

        return NewService

    @classmethod
    async def check_perm(
            cls,
            bot: Bot,
            event: Event,
            stack: Optional[AsyncExitStack] = None,
            dependency_cache: Optional[T_DependencyCache] = None,
    ) -> bool:
        """检查是否满足触发权限

        参数:
            bot: Bot 对象
            event: 上报事件
            stack: 异步上下文栈
            dependency_cache: 依赖缓存

        返回:
            是否满足权限
        """
        return await cls.matcher.check_perm(bot, event, stack, dependency_cache)

    @classmethod
    async def check_rule(
            cls,
            bot: Bot,
            event: Event,
            state: T_State,
            stack: Optional[AsyncExitStack] = None,
            dependency_cache: Optional[T_DependencyCache] = None,
    ) -> bool:
        """检查是否满足匹配规则

        参数:
            bot: Bot 对象
            event: 上报事件
            state: 当前状态
            stack: 异步上下文栈
            dependency_cache: 依赖缓存

        返回:
            是否满足匹配规则
        """
        return await cls.matcher.check_rule(bot, event, state, stack, dependency_cache)

    @classmethod
    def type_updater(cls, func: T_TypeUpdater) -> T_TypeUpdater:
        """装饰一个函数来更改当前事件响应器的默认响应事件类型更新函数

        参数:
            func: 响应事件类型更新函数
        """
        return cls.matcher.type_updater(func)

    @classmethod
    def permission_updater(cls, func: T_PermissionUpdater) -> T_PermissionUpdater:
        """装饰一个函数来更改当前事件响应器的默认会话权限更新函数

        参数:
            func: 会话权限更新函数
        """
        return cls.matcher.permission_updater(func)

    @classmethod
    def append_handler(
            cls, handler: T_Handler, parameterless: Optional[List[Any]] = None
    ) -> Dependent[Any]:
        return cls.matcher.append_handler(handler, parameterless)

    @classmethod
    def handle(
            cls, parameterless: Optional[List[Any]] = None
    ) -> Callable[[T_Handler], T_Handler]:
        """装饰一个函数来向事件响应器直接添加一个处理函数

        参数:
            parameterless: 非参数类型依赖列表
        """
        return cls.matcher.handle(parameterless)

    @classmethod
    def receive(
            cls, id: str = "", parameterless: Optional[List[Any]] = None
    ) -> Callable[[T_Handler], T_Handler]:
        """装饰一个函数来指示 NoneBot 在接收用户新的一条消息后继续运行该函数

        参数:
            id: 消息 ID
            parameterless: 非参数类型依赖列表
        """
        return cls.matcher.receive(id, parameterless)

    @classmethod
    def got(
            cls,
            key: str,
            prompt: Optional[Union[str, Message, MessageSegment, MessageTemplate]] = None,
            parameterless: Optional[List[Any]] = None,
    ) -> Callable[[T_Handler], T_Handler]:
        """装饰一个函数来指示 NoneBot 获取一个参数 `key`

        当要获取的 `key` 不存在时接收用户新的一条消息再运行该函数，如果 `key` 已存在则直接继续运行

        参数:
            key: 参数名
            prompt: 在参数不存在时向用户发送的消息
            parameterless: 非参数类型依赖列表
        """
        return cls.matcher.got(key, prompt, parameterless)

    @classmethod
    async def send(
            cls,
            message: Union[str, Message, MessageSegment, MessageTemplate],
            **kwargs: Any,
    ) -> Any:
        """发送一条消息给当前交互用户

        参数:
            message: 消息内容
            kwargs: {ref}`nonebot.adapters.Bot.send` 的参数，请参考对应 adapter 的 bot 对象 api
        """
        return cls.matcher.send(message, **kwargs)

    @classmethod
    async def finish(
            cls,
            message: Optional[Union[str, Message, MessageSegment, MessageTemplate]] = None,
            **kwargs,
    ) -> NoReturn:
        """发送一条消息给当前交互用户并结束当前事件响应器

        参数:
            message: 消息内容
            kwargs: {ref}`nonebot.adapters.Bot.send` 的参数，请参考对应 adapter 的 bot 对象 api
        """
        await cls.matcher.finish(message, **kwargs)

    @classmethod
    async def pause(
            cls,
            prompt: Optional[Union[str, Message, MessageSegment, MessageTemplate]] = None,
            **kwargs,
    ) -> NoReturn:
        """发送一条消息给当前交互用户并暂停事件响应器，在接收用户新的一条消息后继续下一个处理函数

        参数:
            prompt: 消息内容
            kwargs: {ref}`nonebot.adapters.Bot.send` 的参数，请参考对应 adapter 的 bot 对象 api
        """
        await cls.matcher.pause(prompt, **kwargs)

    @classmethod
    async def reject(
            cls,
            prompt: Optional[Union[str, Message, MessageSegment, MessageTemplate]] = None,
            **kwargs,
    ) -> NoReturn:
        """最近使用 `got` / `receive` 接收的消息不符合预期，
        发送一条消息给当前交互用户并将当前事件处理流程中断在当前位置，在接收用户新的一个事件后从头开始执行当前处理函数

        参数:
            prompt: 消息内容
            kwargs: {ref}`nonebot.adapters.Bot.send` 的参数，请参考对应 adapter 的 bot 对象 api
        """
        await cls.matcher.reject(prompt, **kwargs)

    @classmethod
    async def reject_arg(
            cls,
            key: str,
            prompt: Optional[Union[str, Message, MessageSegment, MessageTemplate]] = None,
            **kwargs,
    ) -> NoReturn:
        """最近使用 `got` 接收的消息不符合预期，
        发送一条消息给当前交互用户并将当前事件处理流程中断在当前位置，在接收用户新的一条消息后从头开始执行当前处理函数

        参数:
            key: 参数名
            prompt: 消息内容
            kwargs: {ref}`nonebot.adapters.Bot.send` 的参数，请参考对应 adapter 的 bot 对象 api
        """
        await cls.matcher.reject_arg(key, prompt, **kwargs)

    @classmethod
    async def reject_receive(
            cls,
            id: str = "",
            prompt: Optional[Union[str, Message, MessageSegment, MessageTemplate]] = None,
            **kwargs,
    ) -> NoReturn:
        """最近使用 `receive` 接收的消息不符合预期，
        发送一条消息给当前交互用户并将当前事件处理流程中断在当前位置，在接收用户新的一个事件后从头开始执行当前处理函数

        参数:
            id: 消息 id
            prompt: 消息内容
            kwargs: {ref}`nonebot.adapters.Bot.send` 的参数，请参考对应 adapter 的 bot 对象 api
        """
        await cls.matcher.reject_receive(id, prompt, **kwargs)

    @classmethod
    def skip(cls) -> NoReturn:
        """跳过当前事件处理函数，继续下一个处理函数

        通常在事件处理函数的依赖中使用。
        """
        cls.matcher.skip()

    def __getattr__(self, item: T) -> T:
        return getattr(self.matcher, item)


@run_preprocessor
async def _(matcher: Matcher, event: OneBotEvent, bot: OneBotBot):
    NewService = services_dict.get(id(type(matcher)), None)
    if not NewService:
        return

    service = NewService()
    config = ServiceConfig(f"{service.matcher.plugin.module_name}.{service.service_name}",
                           service.cd,
                           service.limit,
                           service.enable_on_default,
                           service.invisible)

    if await SUPERUSER(bot, event):
        return

    if hasattr(event, 'group_id') and not config.is_enable_in_group(event.group_id):
        raise IgnoredException(f"Service {service} is not enabled in group {event.group_id}")

    # CD check
    if service.cd != 0 and not await config.check_if_cd_available(event):
        # To-Do: Set Prompt Message
        print("CD!!!!!")
        raise IgnoredException("")
        """if ... is not None:
                await matcher.send(...)
            else:
                raise IgnoredException(f"Service {service} is still in cooldown")"""

    # limit check
    if service.limit != 0 and not await config.check_if_limit_available(event):
        # To-Do: Set Prompt Message
        print("Limit!!!!!")
        raise IgnoredException("")
        """if ... is not None:
                await matcher.send(...)
            else:
                raise IgnoredException(f"Service {service} is still in cooldown")"""
    return


"""
def from_full_name_to_Service(name: str) -> Iterator:
    return filter(lambda x: f"{x.matcher.plugin.module_name}.{x.service_name}" == name, services + scheduler_services)
"""


def from_short_name_to_Service(name: str) -> Iterator:
    return filter(lambda x: x.service_name == name, services + scheduler_services)


@enable_.handle()
@disable_.handle()
async def _(state: T_State, arg: OneBotMessage = CommandArg()):
    if arg:
        state['services'] = arg.extract_plain_text()


@enable_.got("services", prompt="你想要开启什么服务呢?")
async def _(event: GroupMessageEvent, service: OneBotMessage = Arg('services')):
    prepare_to_enable_services = str(service).strip().split(' ')
    error_services = []
    for prepare_to_enable_service in prepare_to_enable_services:
        if prepare_to_enable_service in ['all', 'All', '全部']:
            for x in services:
                ServiceConfig(f"{x.matcher.plugin.module_name}.{x.service_name}",
                              x.cd,
                              x.limit,
                              x.enable_on_default,
                              x.invisible).enable_service(event.group_id)
            for x in scheduler_services:
                ServiceConfig(x.full_name,
                              enable_on_default=x.enable_on_default,
                              invisible=x.invisible,
                              help_=x.help_).enable_service(event.group_id)
            break
        try:
            service_Service = next(from_short_name_to_Service(prepare_to_enable_service))
            if isinstance(service_Service, Service):
                ServiceConfig(f"{service_Service.matcher.plugin.module_name}.{service_Service.service_name}",
                              service_Service.cd,
                              service_Service.limit,
                              service_Service.enable_on_default,
                              service_Service.invisible).enable_service(event.group_id)
            elif isinstance(service_Service, SchedulerServiceMeta):
                ServiceConfig(service_Service.full_name,
                              enable_on_default=service_Service.enable_on_default,
                              invisible=service_Service.invisible,
                              help_=service_Service.help_).enable_service(event.group_id)
        except StopIteration:
            error_services.append(prepare_to_enable_service)
    if error_services:
        await enable_.send("开启" + " ".join(error_services) + "失败!")
    if success_services := set(prepare_to_enable_services).difference(set(error_services)):
        await enable_.finish("成功开启" + " ".join(success_services) + "!")


@disable_.got("services", prompt="你想要关闭什么服务呢?")
async def _(event: GroupMessageEvent, service: OneBotMessage = Arg('services')):
    prepare_to_disable_services = str(service).strip().split(' ')
    error_services = []
    for prepare_to_disable_service in prepare_to_disable_services:
        if prepare_to_disable_service in ['all', 'All', '全部']:
            for x in services:
                ServiceConfig(f"{x.matcher.plugin.module_name}.{x.service_name}",
                              x.cd,
                              x.limit,
                              x.enable_on_default,
                              x.invisible).disable_service(event.group_id)
            for x in scheduler_services:
                ServiceConfig(x.full_name,
                              enable_on_default=x.enable_on_default,
                              invisible=x.invisible,
                              help_=x.help_).disable_service(event.group_id)
            break
        try:
            service_Service = next(from_short_name_to_Service(prepare_to_disable_service))
            if isinstance(service_Service, Service):
                ServiceConfig(f"{service_Service.matcher.plugin.module_name}.{service_Service.service_name}",
                              service_Service.cd,
                              service_Service.limit,
                              service_Service.enable_on_default,
                              service_Service.invisible).disable_service(event.group_id)
            elif isinstance(service_Service, SchedulerServiceMeta):
                ServiceConfig(service_Service.full_name,
                              enable_on_default=service_Service.enable_on_default,
                              invisible=service_Service.invisible,
                              help_=service_Service.help_).disable_service(event.group_id)
        except StopIteration:
            error_services.append(prepare_to_disable_service)
    if error_services:
        await enable_.send("关闭" + " ".join(error_services) + "失败!")
    if success_services := set(prepare_to_disable_services).difference(set(error_services)):
        await enable_.finish("成功关闭" + " ".join(success_services) + "!")
