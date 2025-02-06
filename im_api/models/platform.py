from enum import Enum

class Platform(Enum):
    """平台类型"""
    MINECRAFT = "minecraft"  # Minecraft平台
    QQ = "qq"            # QQ平台
    KOOK = "kook"        # KOOK平台
    DISCORD = "discord"  # Discord平台
    TELEGRAM = "telegram" # Telegram平台
    
    @classmethod
    def from_string(cls, value: str) -> 'Platform':
        try:
            return cls(value.lower())
        except ValueError:
            raise ValueError(f"Unknown platform: {value}")

# 导出
__all__ = ["Platform"] 