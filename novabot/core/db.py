import pymongo
from nonebot import get_driver
from pydantic import BaseModel, Extra


class Config(BaseModel, extra=Extra.ignore):
    mongodb_url: str = "mongodb://localhost:27017"


config = Config.parse_obj(get_driver().config)

DB = pymongo.MongoClient(config.mongodb_url)["NovaBot"]
