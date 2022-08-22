from typing import TypeVar
from nonebot.adapters import Message, MessageSegment

TypeMessage = TypeVar('TypeMessage', str, Message, MessageSegment)
