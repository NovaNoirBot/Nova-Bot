from collections import defaultdict
from typing import List, TYPE_CHECKING, Optional, Dict
from pydantic import BaseModel, Extra

from novabot.core.types import TypeMessage

if TYPE_CHECKING:
    from .service import Service


class InfoModel(BaseModel, extra=Extra.ignore):
    enable_on_default: Optional[bool] = True
    cd: Optional[int] = 0
    limit: Optional[int] = 0
    cd_prompt: Optional[TypeMessage] = None
    limit_prompt: Optional[TypeMessage] = None


class BundleModel(InfoModel, extra=Extra.ignore):
    services: List[Optional["Service"]] = []
    help_: Optional[TypeMessage] = None


class DatabaseModel(BaseModel, extra=Extra.ignore):
    name: str
    cd: Dict[str, Dict[str, float]] = defaultdict(dict)  # group_id: {user_id: cd_timestamp}
    limit: Dict[str, Dict[str, Dict[str, int | float]]] = defaultdict(dict)
    """ limit: group_id: {user_id: {limit: count, date: timestamp}} """


class PluginModel(BaseModel, extra=Extra.ignore):
    bundles: Dict[str, BundleModel] = {}
    plugin_name: Optional[TypeMessage]
    help_: Optional[TypeMessage] = None
