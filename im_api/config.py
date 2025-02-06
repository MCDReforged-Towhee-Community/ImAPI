import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional
import yaml

from im_api.models.platform import Platform


class ConnectionType(Enum):
    """连接类型"""
    WS_SERVER = "ws_server"
    WS_CLIENT = "ws_client"
    HTTP = "http"

@dataclass
class WSServerConfig:
    """反向WebSocket配置"""
    host: str = "0.0.0.0"
    port: int = 8080
    access_token: str = ""
    url_prefix: str = "/ws/"  # WebSocket URL前缀


@dataclass
class WsClientConfig:
    """正向WebSocket配置"""
    ws_url: str = "ws://127.0.0.1:6700"
    access_token: str = ""
    heartbeat: int = 30

class DriverConfig:
    """驱动配置基类"""
    enabled: bool = False
    platform: Platform
    
    def __init__(self, enabled: bool, platform: str):
        self.enabled = enabled
        self.platform = Platform(platform)
    

class QQConfig(DriverConfig):
    """QQ驱动配置"""
    connection_type: ConnectionType = ConnectionType.WS_SERVER
    client: WsClientConfig = WsClientConfig()
    server: WSServerConfig = WSServerConfig()
    
    def __init__(self, enabled: bool, platform: str, connection_type: str, client: dict, server: dict):
        super().__init__(enabled, platform)
        self.connection_type = ConnectionType(connection_type)
        self.client = WsClientConfig(**client)
        self.server = WSServerConfig(**server)


class TelegramConfig(DriverConfig):
    """TG驱动配置"""
    token: str
    http_proxy: str
    
    def __init__(self, enabled: bool, token: str, http_proxy: str):
        super().__init__(enabled, Platform.TELEGRAM)
        self.token = token
        self.http_proxy = http_proxy

class ImAPIConfig:
    """ImAPI配置"""
    drivers: List[DriverConfig] = []
    
    def __init__(self, drivers: List[DriverConfig]):
        self.drivers = drivers

    @classmethod
    def load(cls, mcdr_work_dir: Path) -> 'ImAPIConfig':
        """从配置目录加载配置
        
        Args:
            mcdr_work_dir: MCDR工作目录路径
            
        Returns:
            加载的配置对象
        """
        # MCDR配置目录中的插件配置目录
        config_dir = mcdr_work_dir / 'config' / 'im_api'
        config_dir.mkdir(parents=True, exist_ok=True)

        # 配置文件路径
        config_file = config_dir / 'config.yml'

        # 如果配置文件不存在，从默认配置创建
        if not config_file.exists():
            try:
                import pkg_resources
                # 从包内读取默认配置
                default_config_content = pkg_resources.resource_string(
                    'im_api', 'config.default.yml'
                ).decode('utf-8')
                
                # 写入配置文件
                with open(config_file, 'w', encoding='utf-8') as f:
                    f.write(default_config_content)
            except Exception as e:
                raise FileNotFoundError(f"Failed to create config file: {e}")

        # 加载配置
        with open(config_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}

        # 解析驱动配置
        drivers = []
        for driver_data in data.get('drivers', []):
            platform = driver_data.get('platform', '').lower()
            if platform == 'qq':
                drivers.append(QQConfig(
                    enabled=driver_data.get('enabled', False),
                    platform=platform,
                    connection_type=driver_data.get('connection_type', 'ws_server'),
                    server=driver_data.get('ws_server', {}),
                    client=driver_data.get('ws_client', {})
                ))
            elif platform == 'telegram':
                drivers.append(TelegramConfig(
                    enabled=driver_data.get('enabled', False),
                    token= driver_data.get('token', ''),
                    http_proxy=driver_data.get('http_proxy', '')
                ))

        return cls(drivers=drivers)

    def save(self, plugin_dir: Path) -> None:
        """保存配置到文件
        
        Args:
            plugin_dir: 插件目录路径
        """
        config_dir = plugin_dir / 'config'
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / 'config.yml'

        # 转换配置为字典
        data = {'drivers': []}
        for driver in self.drivers:
            if isinstance(driver, QQConfig):
                driver_data = {
                    'enabled': driver.enabled,
                    'platform': 'qq',
                    'connection_type': driver.connection_type.value,
                    'ws_server': {
                        'host': driver.server.host,
                        'port': driver.server.port,
                        'access_token': driver.server.access_token
                    },
                    'ws_client': {
                        'ws_url': driver.client.ws_url,
                        'access_token': driver.client.access_token,
                        'heartbeat': driver.client.heartbeat
                    }
                }
            elif isinstance(driver, TelegramConfig):
                driver_data = {
                    'enabled': driver.enabled,
                    'platform': 'telegram',
                    'token': driver.token,
                    'http_proxy': driver.http_proxy
                }
            else:
                continue
            data['drivers'].append(driver_data)

        # 保存到文件
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)


# 导出
__all__ = [
    'ImAPIConfig', 'DriverConfig',
    'QQConfig', 'KookConfig', 'DiscordConfig',
    'WSServerConfig', 'WsClientConfig',
    'ConnectionType'
]


    
    
