import json
import os

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "../../configs/models.json")
_config = None

def _load_config():
    global _config
    if _config is None:
        with open(_CONFIG_PATH, "r") as f:
            _config = json.load(f)
    return _config

def resolve_model(name: str) -> str:
    """将模型别名解析为实际模型名称"""
    cfg = _load_config()
    return cfg["aliases"].get(name, name)

def get_default_model(role: str) -> str:
    """获取指定角色的默认模型"""
    cfg = _load_config()
    return cfg["defaults"].get(role, cfg["defaults"]["agent"])
