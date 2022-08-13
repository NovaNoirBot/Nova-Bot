from nonebot import get_driver
from nonebot.adapters.onebot.v11 import MessageEvent, Bot, ActionFailed
from nonebot.rule import Rule

from novabot import on_command

config = get_driver().config
__help__ = """通过回复BOT的发言并输入"撤回"即可撤回bot的发言，用于防止色图炸群刷屏等
    Type: ReplyEvent
用法:
    .withdraw
    撤回
    撤
"""


def _is_reply_to_me(event: MessageEvent):
    return bool(event.reply and
                (event.reply.sender.user_id == event.self_id
                 or
                 event.reply.sender.user_id == event.user_id
                 or
                 str(event.sender.user_id) in config.superusers if config.superusers else False))


with_draw = on_command("撤回",
                       aliases={"撤", ".withdraw"},
                       rule=Rule(_is_reply_to_me),
                       priority=1,
                       block=True,
                       help_=__help__)


@with_draw.handle()
async def _(bot: Bot, event: MessageEvent):
    try:
        await bot.call_api("delete_msg", message_id=event.reply.message_id)
    except ActionFailed:  # Timed-out
        if event.reply.sender.user_id == event.self_id:
            await with_draw.send("已经撤回不了了 QAQ, 找找管理叭")
    try:
        await bot.call_api("delete_msg", message_id=event.message_id)  # Try to withdraw Triggering Message
    except ActionFailed:
        pass
