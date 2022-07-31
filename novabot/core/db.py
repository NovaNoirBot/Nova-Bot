import pymongo
from pydantic import BaseModel, Extra
from nonebot import get_driver


class Config(BaseModel, extra=Extra.ignore):
    mongodb_url: str = "mongodb://localhost:27017"


config = Config.parse_obj(get_driver().config)

DB = pymongo.MongoClient(config.mongodb_url)["NovaBot"]
