import datetime

import pymongo
from typing import Optional, Tuple
from collections import defaultdict
from novabot.core.db import DB

from .model import DatabaseModel

ServiceDB = DB['Service']
ServiceDB.create_index([("name", pymongo.TEXT)])


class ServiceDatabase:
    def __init__(self, name: str):
        self.name = name
        if data := ServiceDB.find_one({"name": self.name}):
            self.data = DatabaseModel.parse_obj(data)
            self.data.cd = defaultdict(dict, self.data.cd)
            self.data.limit = defaultdict(dict, self.data.limit)
        else:
            self.data = DatabaseModel(name=self.name)

    def cd(self, user_id: str, group_id: Optional[str]) -> float:
        return self.data.cd[group_id].get(user_id, 0)

    def limit(self, user_id: str, group_id: Optional[str]) -> Tuple[int, float]:
        return self.data.limit[group_id].get(user_id, {}).get('limit', 0), \
               self.data.limit[group_id].get(user_id, {}).get('date', 0)

    def update_cd(self, user_id: str, group_id: Optional[str], cd: float):
        self.data.cd[group_id][user_id] = cd
        self.update()

    def update_limit(self, user_id: str, group_id: Optional[str]):
        self.data.limit[group_id][user_id] = {
            "limit": self.data.limit[group_id].get(user_id, {}).get('limit', 0) + 1,
            "date": datetime.datetime.now().timestamp()
        }
        self.update()

    def update(self):
        ServiceDB.update_one({"name": self.name}, {"$set": self.data.dict()}, upsert=True)

