import asyncio
import inspect
from contextlib import AsyncExitStack
from datetime import datetime
from typing import Dict, Optional, Type, Union, List, Literal, Tuple
from collections import defaultdict
from nonebot import get_driver, get_loaded_plugins, get_bot
from nonebot.params import DependParam
from nonebot.rule import Rule
from nonebot.message import run_preprocessor
from nonebot.log import logger
from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11 import (
    Event,
    MessageEvent,
    NotifyEvent,
    GroupMessageEvent,
    Bot,
    Message)
from nonebot.typing import T_State, T_DependencyCache

from novabot.core.types import TypeMessage

from .model import BundleModel, InfoModel, PluginModel
from .database import ServiceDatabase

driver = get_driver()

services_dict: Dict[str, PluginModel] = defaultdict(PluginModel)
trigger_to_bundle_dict: Dict[int, Dict[Literal['bundle', 'plugin', 'service'],
                                       Union[BundleModel, PluginModel, 'Service']]] = defaultdict(Dict)
ready_services: List['Service'] = []


class Service:
    def __init__(self,
                 Trigger: Union[Type[Matcher]],  # To-Do: Add Scheduler Trigger
                 bundle: Optional[str] = '_default',
                 *,
                 enable_on_default: Optional[bool] = True,
                 cd: Optional[int] = 0,
                 limit: Optional[int] = 0,
                 cd_prompt: Optional[TypeMessage] = "",
                 limit_prompt: Optional[TypeMessage] = "",
                 independent: Optional[bool] = False,
                 independent_name: Optional[str] = None):
        """

        :param Trigger:
        :param bundle:
        :param enable_on_default:
        :param cd:
        :param limit:
        :param cd_prompt: {cd} is the cooldown format.
        :param limit_prompt:
        :param independent:
        :param independent_name:
        """
        frame = map(lambda x: inspect.getmodule(x[0]), filter(lambda x: x.code_context, inspect.stack()[1:]))
        plugins = get_loaded_plugins()
        plugin = None
        for i in frame:
            plugin = next(filter(lambda x: x.module == i, plugins), None)
            if plugin is not None:
                break
        self.Trigger = Trigger
        self.bundle = bundle
        self.plugin = plugin
        self.data = InfoModel(**locals())
        self.independent = independent
        self.independent_name = independent_name
        if independent and not independent_name:
            raise ValueError("You must set independent_name when independent is True")
        self.name = f"{self.plugin.name}.{self.bundle}{f'.{self.independent_name}' if self.independent else ''}"
        ready_services.append(self)
        _rule_handler(self)

    async def check_cd(self, event: Event) -> Tuple[bool, Optional[float]]:
        if await self.admin_check(event) or not self.data.cd:
            return True, None
        db = ServiceDatabase(self.name)
        cd = db.cd(str(event.user_id), str(event.group_id) if hasattr(event, 'group_id') else '0')
        return datetime.now().timestamp() >= cd, cd - datetime.now().timestamp()

    def update_cd(self, event: Event):
        db = ServiceDatabase(self.name)
        db.update_cd(str(event.user_id), str(event.group_id) if hasattr(event, 'group_id') else '0',
                     datetime.now().timestamp() + self.data.cd)

    async def check_limit(self, event: Event) -> Tuple[bool, Optional[float]]:
        if await self.admin_check(event) or not self.data.limit:
            return True, None
        db = ServiceDatabase(self.name)
        limit, date = db.limit(str(event.user_id), str(event.group_id) if hasattr(event, 'group_id') else '0')
        delta = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - \
                datetime.fromtimestamp(date).replace(hour=0, minute=0, second=0, microsecond=0)
        if delta.days > 0:
            return True, None
        return self.data.limit > limit, self.data.limit - limit

    def update_limit(self, event: Event):
        db = ServiceDatabase(self.name)
        db.update_limit(str(event.user_id), str(event.group_id) if hasattr(event, 'group_id') else '0')

    @staticmethod
    async def admin_check(event: Event) -> bool:
        if not isinstance(event, (MessageEvent, NotifyEvent)):  # To-Do: add more event types
            return True
        if isinstance(event, NotifyEvent):
            role = await get_bot(str(event.self_id)).call_api("get_group_member_info",
                                                              group_id=event.group_id,
                                                              user_id=event.user_id)
            if role in ['admin', 'owner']:
                return True
        elif isinstance(event, GroupMessageEvent) and event.sender.role in ['admin', 'owner']:
            return True
        return False

    def __repr__(self):
        return f"<service of {self.plugin.name}, " \
               f"bundle={self.bundle}, Trigger={self.Trigger}, " \
               f"data={self.data}>"

    def __str__(self):
        return self.__repr__()


@driver.on_startup
async def _():
    for service in ready_services:
        name = service.plugin.metadata.name if service.plugin.metadata else service.plugin.name
        if not services_dict.get(name):
            services_dict[name] = PluginModel(plugin_name=name)
        if not services_dict[name].bundles.get(service.bundle):
            services_dict[name].bundles[service.bundle] = BundleModel()
        bundles = services_dict[name].bundles[service.bundle]
        bundles.services.append(service)
        bundles.parse_obj(service.data)
        trigger_to_bundle_dict[id(service.Trigger)] = {
            "bundle": bundles,
            "plugin": services_dict[name],
            "service": service
        }
        logger.opt(colors=True).success(f'<y>{service}</y> loaded.')


@run_preprocessor
async def _(matcher: Matcher):
    matcher_dict = trigger_to_bundle_dict.get(id(type(matcher)), None)
    if not matcher_dict:
        return


def _rule_handler(service: Service) -> None:
    if not isinstance(service.Trigger, type(Matcher)):
        return

    async def _rule(bot: Bot,
                    event: Event,
                    state: T_State,
                    stack: Optional[AsyncExitStack] = None) -> bool:
        return await _cd_rule(bot, event) and await _limit_rule(bot, event) \
            if await _rules(bot=bot, event=event, state=state, stack=stack) else False

    async def _cd_rule(bot: Bot,
                       event: Event) -> bool:
        available, cd = await service.check_cd(event)
        if available:
            service.update_cd(event)
        elif service.data.cd_prompt:
            msg = Message.template(Message(service.data.cd_prompt)).format(cd=cd,
                                                                           user=event.user_id or 0) or ''
            await bot.send(event, msg)
        return available

    async def _limit_rule(bot: Bot,
                          event: Event) -> bool:
        available, limit = await service.check_limit(event)
        if available:
            service.update_limit(event)
        elif service.data.limit_prompt:
            msg = Message.template(Message(service.data.limit_prompt)).format(limit=limit,
                                                                              user=event.user_id or 0) or ''
            await bot.send(event, msg)
        return available

    _matcher = service.Trigger
    _rules = Rule(*_matcher.rule.checkers)
    _matcher.rule = Rule(_rule)
