import os
import json
from typing import Any, Dict, Optional

from mcdreforged.api.types import PluginServerInterface, CommandSource, Info
from mcdreforged.api.command import Literal

from im_api.config import ImAPIConfig
from im_api.core.driver import DriverManager
from im_api.core.processor import EventProcessor
from im_api.core.bridge import MessageBridge
from im_api.core.context import Context
from im_api.drivers.qq import QQDriver
from im_api.drivers.base import Platform
from im_api.drivers.tg import TeleGramDriver

class ImAPI:
    """ImAPI 插件主类"""

    PLUGIN_ID = "im_api"

    def __init__(self, server: PluginServerInterface):
        self.server = server
        self.logger = server.logger
        self.config = self._load_config()

        # 初始化管理器
        self.driver_manager = DriverManager()
        self.message_bridge = MessageBridge(self.server, self.driver_manager)
        self.event_processor = EventProcessor(self.server, self.driver_manager, self.message_bridge)
        
        # 注册驱动
        self.driver_manager.register_driver(Platform.QQ, QQDriver).register_driver(Platform.TELEGRAM, TeleGramDriver)

    def _load_config(self) -> ImAPIConfig:
        """加载配置文件"""
        return Context.get_instance().load_config()

    def load(self) -> bool:
        """加载插件"""
        self.logger.info("Loading ImAPI...")
        if self.config is None:
            self.logger.error("Failed to load configuration")
            return False

        # 并行加载驱动
        try:
            self.driver_manager.load_drivers_parallel(self.config.drivers)
        except Exception as e:
            self.logger.error(f"Failed to load drivers: {e}")
            return False
        # 注册驱动回调
        self.driver_manager.register_callbacks(
            lambda platform, msg: self.event_processor.on_message(platform, msg),
            lambda platform, evt: self.event_processor.on_event(platform, evt)
        )

        # 注册命令
        self.server.register_help_message("!!im", "ImAPI commands")
        self.server.register_command(
            Literal("!!im").
            then(
                Literal("status").
                runs(lambda src: self.show_status(src))
            )
        )

        self.logger.info("ImAPI loaded successfully")
        return True

    def unload(self):
        """卸载插件"""
        self.logger.info("Unloading ImAPI...")
        # 先关闭所有驱动
        self.driver_manager.shutdown()
        # 等待一段时间确保资源被释放
        import time
        time.sleep(1)
        self.logger.info("ImAPI unloaded successfully")

    # def reload(self, source: CommandSource):
    #     """重载插件"""
    #     self.logger.info("Reloading ImAPI...")
    #     # 先卸载旧实例
    #     self.unload()
    #     # 重新加载配置
    #     self.config = self._load_config()
    #     # 重新加载插件
    #     self.load()
    #     source.reply("ImAPI reloaded successfully")

    def show_status(self, source: CommandSource):
        """显示插件状态"""
        drivers = self.driver_manager.get_all_drivers()
        if not drivers:
            source.reply("No drivers loaded")
            return

        status = ["ImAPI Status:"]
        for driver in drivers:
            status.append(
                f"- {driver.get_platform()}: {'Connected' if driver.connected else 'Disconnected'}")
        source.reply("\n".join(status))


def on_load(server: PluginServerInterface, old_module):
    """插件加载入口"""
    # 初始化上下文
    context = Context.get_instance()
    context.initialize(server)
    
    # 如果是热重载，先卸载旧实例
    if old_module is not None:
        old_api = context.get_api()
        if old_api is not None:
            old_api.unload()
            context.set_api(None)
    
    # 创建新实例并加载
    api = ImAPI(server)
    if not api.load():
        return server.unload_plugin(ImAPI.PLUGIN_ID)
    context.set_api(api)  # 加载完成后再设置到 Context 中
    
    return api


def on_unload(server: PluginServerInterface):
    """插件卸载入口"""
    context = Context.get_instance()
    if context.is_initialized():
        server.logger.info("Unloading ImAPI plugin...")
        api = context.get_api()
        if api is not None:
            api.unload()
            context.set_api(None)
        context.reset_instance()
        server.logger.info("ImAPI plugin unloaded")
