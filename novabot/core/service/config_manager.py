from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Union, Optional

import pymongo
from nonebot import get_bot
from nonebot.adapters.onebot.v11 import Event, GroupMessageEvent, MessageEvent, NotifyEvent
from nonebot.log import logger

from novabot.core.db import DB

ServiceMongoDB = DB['services']
ServiceMongoDB.create_index([("service_name", pymongo.TEXT)])


@dataclass
class ServiceDatabase:
    service_name: str
    cd: int
    limit: int
    enable_on_default: bool
    invisible: bool
    help_: str
    enable_groups: List[int]
    disable_groups: List[int]
    cd_dict: Dict[str, Dict[str, float]]
    limit_dict: Dict[str, Dict[str, Dict[str, Union[str, float]]]]


class ServiceConfig:
    def __init__(self,
                 name: str,
                 cd: Optional[int] = 0,
                 limit: Optional[int] = 0,
                 enable_on_default: Optional[bool] = True,
                 invisible: Optional[bool] = False,
                 help_: Optional[str] = None,
                 force: Optional[bool] = False
                 ):
        self.name = name
        try:
            n = next(ServiceMongoDB.find({"service_name": self.name}), None)
            if not n or force:
                self.data = initialize_ServiceConfig(name, cd, limit, enable_on_default, invisible, help_)
                ServiceMongoDB.insert_one(self.data.__dict__)
            else:
                n.pop("_id")
                self.data = ServiceDatabase(**n)

        except TypeError:  # For Update
            new_data = initialize_ServiceConfig(name, cd, limit, enable_on_default, invisible, help_).__dict__
            n = next(ServiceMongoDB.find({"service_name": self.name}))
            new_data.update(n)
            new_data.pop("_id")
            self.data = ServiceDatabase(**new_data)
            ServiceMongoDB.update_one({"service_name": self.name},
                                      {"$set": new_data})
        except Exception as e:
            logger.error(str(type(e)) + str(e))

    def _update(self) -> bool:
        if self.data.__dict__.get('_id'):
            self.data.__dict__.pop("_id")
        return bool(ServiceMongoDB.update_one({"service_name": self.name},
                                              {"$set": self.data.__dict__}))

    def enable_service(self, grp_id: int) -> bool:
        try:
            self.data.disable_groups.remove(grp_id)
        except ValueError:
            pass
        x = set(self.data.enable_groups)
        x.add(grp_id)
        self.data.enable_groups = list(x)
        return self._update()

    def disable_service(self, grp_id: int) -> bool:
        try:
            self.data.enable_groups.remove(grp_id)
        except ValueError:
            pass
        x = set(self.data.disable_groups)
        x.add(grp_id)
        self.data.disable_groups = list(x)
        return self._update()

    def _show_db(self) -> List[Union[Dict, None]]:
        n = ServiceMongoDB.find({"service_name": self.name})
        return [dict(x) for x in n]

    def is_enable_in_group(self, grp_id: int) -> bool:
        return (grp_id in self.data.enable_groups) \
               or \
               (grp_id not in self.data.disable_groups and self.data.enable_on_default)

    async def check_if_cd_available(self, event: Event, reset: bool = True) -> bool:
        available = True
        if isinstance(event, (MessageEvent, NotifyEvent)):
            if isinstance(event, NotifyEvent):
                role = await get_bot(str(event.self_id)).call_api("get_group_member_info",
                                                                  group_id=event.group_id,
                                                                  user_id=event.user_id)
                if role in ['admin', 'owner']:
                    return True
            elif isinstance(event, GroupMessageEvent) and event.sender.role in ['admin', 'owner']:
                return True
            available = self._check_if_cd_available(event.user_id,
                                                    event.group_id if hasattr(event, 'group_id') else 0)
            if available and reset:
                self._update_cd(event.user_id,
                                event.group_id if hasattr(event, 'group_id') else 0)
        return available

    def _check_if_cd_available(self, usr_id: int, grp_id: Optional[int] = 0) -> bool:
        grp_id = str(grp_id)
        usr_id = str(usr_id)
        grp_cd_dict = self.data.cd_dict.get(grp_id, {})
        cd = grp_cd_dict.get(usr_id, 0)
        return datetime.now().timestamp() - cd > self.data.cd

    def _update_cd(self, usr_id: int, grp_id: Optional[int] = 0):
        grp_id = str(grp_id)
        usr_id = str(usr_id)
        grp_cd_dict = self.data.cd_dict.get(grp_id, {})
        grp_cd_dict[usr_id] = datetime.now().timestamp()
        self.data.cd_dict[grp_id] = grp_cd_dict
        self._update()

    async def check_if_limit_available(self, event, reset: bool = True):
        available = True
        if isinstance(event, (MessageEvent, NotifyEvent)):
            if isinstance(event, NotifyEvent):
                role = await get_bot(str(event.self_id)).call_api("get_group_member_info",
                                                                  group_id=event.group_id,
                                                                  user_id=event.user_id)
                if role in ['admin', 'owner']:
                    return True
            elif isinstance(event, GroupMessageEvent) and event.sender.role in ['admin', 'owner']:
                return True
            available = self._check_if_limit_available(event.user_id,
                                                       event.group_id if hasattr(event, 'group_id') else 0)
            if available and reset:
                self._update_limit(event.user_id,
                                   event.group_id if hasattr(event, 'group_id') else 0)
        return available

    def _check_if_limit_available(self, usr_id: int, grp_id: Optional[int] = 0) -> bool:
        grp_id = str(grp_id)
        usr_id = str(usr_id)
        grp_limit_dict = self.data.limit_dict.get(grp_id, {})
        limit_dict = grp_limit_dict.get(usr_id, {})
        limit = limit_dict.get('limit', 0)
        date = limit_dict.get('date', datetime(2000, 1, 1).timestamp())
        if datetime.now().day - datetime.fromtimestamp(date).day > 0 \
                or (datetime.now() - datetime.fromtimestamp(date)).days > 0:
            return True
        return limit < self.data.limit

    def _update_limit(self, usr_id: int, grp_id: Optional[int] = 0):
        grp_id = str(grp_id)
        usr_id = str(usr_id)
        grp_limit_dict = self.data.limit_dict.get(grp_id, {})
        limit_dict = grp_limit_dict.get(usr_id, {})
        limit = limit_dict.get('limit', 0)
        date = limit_dict.get('date', datetime(2000, 1, 1).timestamp())
        if datetime.now().day - datetime.fromtimestamp(date).day > 0 \
                or (datetime.now() - datetime.fromtimestamp(date)).days > 0:
            limit_dict["limit"] = 1
            limit_dict["date"] = datetime.now().timestamp()
        else:
            limit_dict["limit"] = limit + 1
            limit_dict["date"] = date
        grp_limit_dict[usr_id] = limit_dict
        self.data.limit_dict[grp_id] = grp_limit_dict
        self._update()


def initialize_ServiceConfig(name: str,
                             cd: int,
                             limit: int,
                             enable_on_default: bool,
                             invisible: bool,
                             help_: str) -> ServiceDatabase:
    return ServiceDatabase(name, cd, limit, enable_on_default, invisible, help_, [], [], {}, {})
