from telegram import Update, ChatMember, ChatMemberUpdated, Chat
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, Application, ChatMemberHandler, CommandHandler
from mcdreforged.api.all import *
from typing import Optional
import threading

from im_api.config import TelegramConfig
from im_api.drivers.base import BaseDriver, Platform
from im_api.models.message import Message, Event, User, Channel
from im_api.models.request import ChannelInfo, SendMessageRequest, MessageType

class TeleGramDriver(BaseDriver):
    """Telegram 驱动实现"""
    application: Application
    @classmethod
    def get_platform(cls) -> Platform:
        return Platform.TELEGRAM
    
    def __init__(self, config: TelegramConfig):
        super().__init__(config)
        self.token = config.token
        self.proxy_url = config.http_proxy  # 默认代理设置
        self.application = None
        self.event_loop = None  # 添加事件循环引用
        self.stop_event = threading.Event()  # 添加停止事件
        
    async def handle_message(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """处理消息事件"""
        if not update.message:
            return
            
        message = Message(
            id=str(update.message.message_id),
            content=update.message.text,
            channel=Channel(
                id=str(update.effective_chat.id),
                type="group" if update.effective_chat.type in ["group", "supergroup"] else "private",
                name=update.effective_chat.title
            ),
            user=User(
                id=str(update.effective_user.id),
                name=update.effective_user.full_name,
                avatar=None  # Telegram不直接提供头像URL
            ),
            platform=Platform.TELEGRAM
        )
        
        if self.message_callback:
            self.message_callback(Platform.TELEGRAM, message)

    async def handle_chat_member(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """处理群组成员变更事件"""
        if not update.chat_member:
            return
        self.logger.debug(f'update_chat_member: {update}')
        # 确定事件类型
        event_type = None
        if update.chat_member.new_chat_member and update.chat_member.new_chat_member.status == "member":
            event_type = "guild.member.join"
        elif update.chat_member.old_chat_member and update.chat_member.old_chat_member.status == "member" and \
             update.chat_member.new_chat_member and update.chat_member.new_chat_member.status == "left":
            event_type = "guild.member.leave"
        
        if not event_type:
            return

        # 创建事件对象
        event = Event(
            id=str(update.chat_member.date.timestamp()),
            type=event_type,
            platform=Platform.TELEGRAM,
            channel=Channel(
                id=str(update.chat_member.chat.id),
                type="group" if update.chat_member.chat.type in ["group", "supergroup"] else "private",
                name=update.chat_member.chat.title
            ),
            user=User(
                id=str(update.chat_member.new_chat_member.user.id),
                name=update.chat_member.new_chat_member.user.full_name,
                avatar=None
            )
        )
        # 触发事件回调
        if self.event_callback:
            self.event_callback(Platform.TELEGRAM, event)
                    
    def connect(self) -> None:
        """连接到Telegram平台"""
        if self.connected:
            return
            
        def start_bot():
            import asyncio
            loop = asyncio.new_event_loop()
            self.event_loop = loop  # 保存事件循环引用
            asyncio.set_event_loop(loop)
            try:
                builder = ApplicationBuilder().token(self.token)
                if self.proxy_url is not None:
                    builder = builder.proxy(self.proxy_url).get_updates_proxy(self.proxy_url)
                self.application = builder.build()
                # 注册消息处理器
                self.application.add_handler(MessageHandler(filters.TEXT, self.handle_message))
                self.application.add_handler(ChatMemberHandler(self.handle_chat_member, ChatMemberHandler.CHAT_MEMBER))
                # 创建停止检查线程
                def check_stop():
                    asyncio.set_event_loop(loop)
                    while True:
                        if self.stop_event.is_set():
                            self.logger.warn('Telegram bot stopping')
                            self.event_loop.stop()
                            self.logger.warn('Telegram bot stopped')
                            break
                        time.sleep(0.5)
                
                # 启动停止检查线程
                stop_thread = threading.Thread(target=check_stop, daemon=True)
                stop_thread.start()
                self.application.run_polling(stop_signals=None, allowed_updates=Update.ALL_TYPES)
            except Exception as e:
                print(e)
                self.logger.error(f"Failed to connect Telegram driver: {e}")
                self.connected = False  # 确保连接状态正确
                
        # 在后台线程中启动机器人
        import threading
        self.bot_thread = threading.Thread(target=start_bot, daemon=True)
        self.bot_thread.start()
        self.logger.info("Telegram driver connected successfully")
        # 等待连接建立
        import time
        start_time = time.time()
        while (not self.application or not self.application.running) and time.time() - start_time < 10:  # 最多等待10秒
            time.sleep(0.1)
        if not self.application or not self.application.running:
            self.logger.error("Failed to connect Telegram driver: timeout")
        self.connected = True
    
    def disconnect(self) -> None:
        """断开与Telegram平台的连接"""
        if not self.connected:
            return
            
        try:
            # 设置停止事件，通知bot线程停止运行
            self.stop_event.set()
            
            # 等待后台线程结束
            if self.bot_thread and self.bot_thread.is_alive():
                self.bot_thread.join(timeout=5)
            
            self.connected = False
            self.event_loop = None  # 清理事件循环引用
            self.application = None
            self.stop_event.clear()  # 重置停止事件
            self.logger.info("Telegram driver disconnected")
        except Exception as e:
            self.logger.error(f"Error disconnecting Telegram driver: {e}")
    
    def send_message(self, request: SendMessageRequest) -> Optional[str]:
        """发送消息到Telegram
        
        Args:
            request: 发送消息请求
            
        Returns:
            消息ID, 如果发送失败则返回 None
        """
        if not self.connected or not self.application:
            self.logger.error("Cannot send message: driver not connected")
            return None
        async def _send_message():
            return await self.application.bot.send_message(
                chat_id=int(request.channel_id),
                text=request.content
            )
        try:
            import asyncio
            future = asyncio.run_coroutine_threadsafe(_send_message(), self.event_loop)
            # 最多等待5s
            result = future.result(timeout=5)
            return str(result.message_id)
        except Exception as e:
            self.logger.error(f"Error sending message: {e}")
            return None

# 导出
__all__ = ["TeleGramDriver"]
        
    