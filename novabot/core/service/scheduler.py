import inspect
import logging
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.util import undefined
from nonebot import get_driver, get_bot
from nonebot.adapters.onebot.v11 import Bot
from nonebot.exception import MockApiException
from nonebot.log import LoguruHandler, logger
from pydantic import Field, BaseSettings

from novabot.core.service.config_manager import ServiceConfig


class Config(BaseSettings):
    apscheduler_autostart: bool = True
    apscheduler_log_level: int = 30
    apscheduler_config: dict = Field(
        default_factory=lambda: {"apscheduler.timezone": "Asia/Shanghai"}
    )

    class Config:
        extra = "ignore"


@dataclass
class SchedulerServiceMeta:
    service_name: Optional[str]
    full_name: Optional[str]
    help_: Optional[str]
    enable_on_default: bool
    invisible: bool

    def __repr__(self) -> str:
        return (
            f"<SchedulerService of {self.service_name or 'unknown'}, "
            f"enable_on_default={self.enable_on_default}, "
            f"invisible={self.invisible}>"
        )


bot: Optional[Bot] = None
driver = get_driver()
global_config = driver.config
plugin_config = Config(**global_config.dict())
_scheduler = AsyncIOScheduler()
_scheduler.configure(plugin_config.apscheduler_config)


def _get_matcher_module_name(depth: int = 1) -> str:
    current_frame = inspect.currentframe()
    if current_frame is None:
        return ""
    frame = inspect.getouterframes(current_frame)[depth + 1].frame
    return inspect.getmodule(frame).__name__


class ServiceScheduler:
    @staticmethod
    def add_job(func, service_name, trigger=None, args=None, kwargs=None, id=None, name=None,
                misfire_grace_time=undefined, coalesce=undefined, max_instances=undefined,
                next_run_time=undefined, jobstore='default', executor='default',
                replace_existing=False, enable_on_default=True, invisible=False, help_=None, **trigger_args):

        async def blocker(*arg, **kwarg):

            async def blocking(_: Bot, __: str, data: Dict[str, Any]):
                config = ServiceConfig(scheduler_service.full_name,
                                       enable_on_default=scheduler_service.enable_on_default,
                                       invisible=scheduler_service.invisible,
                                       help_=scheduler_service.help_)
                if grp_id := data.get('group_id', None):
                    if not config.is_enable_in_group(grp_id):
                        raise MockApiException(f"Service {config.name} is disabled in group {grp_id}")

            bot._calling_api_hook.add(blocking)
            await func(*arg, **kwarg)
            bot._calling_api_hook.remove(blocking)

        scheduler_service = SchedulerServiceMeta(service_name,
                                                 f"{_get_matcher_module_name()}.{service_name}",
                                                 help_,
                                                 enable_on_default,
                                                 invisible)
        scheduler_services.append(scheduler_service)
        _scheduler.add_job(blocker, trigger, args, kwargs, id, name, misfire_grace_time,
                           coalesce, max_instances, next_run_time, jobstore, executor,
                           replace_existing, **trigger_args)

    def scheduled_job(self, service_name, trigger, args=None, kwargs=None, id=None, name=None,
                      misfire_grace_time=undefined, coalesce=undefined, max_instances=undefined,
                      next_run_time=undefined, jobstore='default', executor='default',
                      enable_on_default=True, invisible=False, help_=None,
                      **trigger_args):
        def inner(func):
            self.add_job(func, service_name, trigger, args, kwargs, id, name, misfire_grace_time, coalesce,
                         max_instances, next_run_time, jobstore, executor, True,
                         enable_on_default, invisible, help_, **trigger_args)
            return func

        return inner


scheduler = ServiceScheduler()
scheduler_services: List[SchedulerServiceMeta] = []


async def _start_scheduler():
    if not _scheduler.running:
        _scheduler.start()
        logger.opt(colors=True).info("<y>ServiceScheduler Started</y>")


async def _shutdown_scheduler():
    if _scheduler.running:
        _scheduler.shutdown()
        logger.opt(colors=True).info("<y>ServiceScheduler Shutdown</y>")


async def _get_bot():
    global bot
    bot = get_bot()


if plugin_config.apscheduler_autostart:
    driver.on_startup(_start_scheduler)
    driver.on_bot_connect(_get_bot)
    driver.on_shutdown(_shutdown_scheduler)

aps_logger = logging.getLogger("apscheduler")
aps_logger.setLevel(plugin_config.apscheduler_log_level)
aps_logger.handlers.clear()
aps_logger.addHandler(LoguruHandler())

__all__ = ['scheduler']
