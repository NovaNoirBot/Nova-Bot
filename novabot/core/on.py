from typing import Union, Tuple, Optional, Set, Type, List

from nonebot.dependencies import Dependent
from nonebot.permission import Permission
from nonebot.plugin.on import (
    on_command as nb_on_command,
    on_message as nb_on_message
)
from nonebot.rule import Rule
from nonebot.typing import T_RuleChecker, T_Handler, T_State, T_PermissionChecker

from novabot.core.plugins.service import Service


def on_command(
        cmd: Union[str, Tuple[str, ...]],
        service_name: str = None,
        rule: Optional[Union[Rule, T_RuleChecker]] = None,
        aliases: Optional[Set[Union[str, Tuple[str, ...]]]] = None,
        *,
        permission: Optional[Union[Permission, T_PermissionChecker]] = None,
        handlers: Optional[List[Union[T_Handler, Dependent]]] = None,
        temp: bool = False,
        priority: int = 1,
        block: bool = True,
        state: Optional[T_State] = None,
        help_: Optional[str] = None,
        cd: int = 0,
        limit: int = 0,
        enable_on_default: bool = True,
        invisible: bool = False,
        _depth: int = 0,
) -> Type[Service]:
    """
    注册一个消息事件响应器，并且当消息以指定命令开头时响应。

    命令匹配规则参考: `命令形式匹配 <rule.md#command-command>`_

    参数:
        cmd: 指定命令内容
        rule: 事件响应规则
        aliases: 命令别名
        permission: 事件响应权限
        handlers: 事件处理函数列表
        temp: 是否为临时事件响应器（仅执行一次）
        priority: 事件响应器优先级
        block: 是否阻止事件向更低优先级传递
        state: 默认 state
    """

    matcher = nb_on_command(cmd, rule, aliases,
                            permission=permission,
                            handlers=handlers,
                            temp=temp,
                            priority=priority,
                            block=block,
                            state=state)
    service = Service.new(
        service_name or cmd,  # Make it easier to migrate plugins
        matcher,
        help_=help_,
        cd=cd,
        limit=limit,
        enable_on_default=enable_on_default,
        invisible=invisible
    )
    return service


def on_message(
    service_name: str,
    rule: Optional[Union[Rule, T_RuleChecker]] = None,
    permission: Optional[Union[Permission, T_PermissionChecker]] = None,
    *,
    handlers: Optional[List[Union[T_Handler, Dependent]]] = None,
    temp: bool = False,
    priority: int = 1,
    block: bool = True,
    state: Optional[T_State] = None,
    help_: Optional[str] = None,
    cd: int = 0,
    limit: int = 0,
    enable_on_default: bool = True,
    invisible: bool = False,
    _depth: int = 0
) -> Type[Service]:
    matcher = nb_on_message(rule,
                            permission,
                            handlers=handlers,
                            temp=temp,
                            priority=priority,
                            block=block,
                            state=state)
    service = Service.new(
        service_name,  # Make it easier to migrate plugins
        matcher,
        help_=help_,
        cd=cd,
        limit=limit,
        enable_on_default=enable_on_default,
        invisible=invisible
    )
    return service
