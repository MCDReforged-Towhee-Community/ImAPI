from typing import Any, Dict, Optional, Callable, List

from mcdreforged.api.all import *

from im_api.core.driver import DriverManager
from im_api.core.context import Context
from im_api.models.message import Event, Message
from im_api.models.platform import Platform
from im_api.models.request import SendMessageRequest, MessageType


class MessageBridge:
    """消息桥接器，负责在 MCDR 和 IM 平台之间转换消息"""

    def __init__(self, server: ServerInterface, driver_manager: DriverManager):
        """初始化消息桥接器"""
        self.server = server
        self.driver_manager = driver_manager
        self.logger = Context.get_instance().logger
        # 注册消息发送事件监听器
        self.server.register_event_listener(
            "im_api.send_message", self.on_send_message)

    def on_send_message(self,server: PluginServerInterface, request: SendMessageRequest) -> List[str]:
        """
        处理消息发送事件
        :param request: 发送消息请求
        :return: 消息ID列表，如果没有成功发送则返回空列表
        """
        # 遍历所有驱动，处理发送请求
        results = []
        plats = request.platforms
        for driver in self.driver_manager.get_all_drivers():
            try:
                # 只响应对应platform的消息事件
                if driver.get_platform() not in plats:
                    self.logger.debug(f'platform {driver.get_platform()} not match, Skip')
                    continue
                result = driver.send_message(request)
                if result:
                    results.append(result)
            except Exception as e:
                self.logger.error(f"Error sending message via driver {driver}: {e}")

        return results


# 导出
__all__ = ["MessageBridge"]
