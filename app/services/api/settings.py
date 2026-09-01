from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from app.database import system_configurations_collection
from app.utils import normalize
import traceback


class SettingsService:

    @staticmethod
    def _group_settings(configs: List[dict]) -> Dict[str, List[dict]]:
        """Helper to group settings by their 'group' field."""
        grouped: Dict[str, List[dict]] = {}
        for config in configs:
            group = config.get("group", "Other")
            if group not in grouped:
                grouped[group] = []
            grouped[group].append(config)
        return grouped

    @staticmethod
    async def get_public_settings() -> Tuple[Optional[Dict[str, List[dict]]], Optional[str]]:
        try:
            configs = await system_configurations_collection.find(
                {"is_public": True}
            ).to_list(length=None)
            normalized_configs = [normalize(conf) for conf in configs]
            grouped = SettingsService._group_settings(normalized_configs)
            return grouped, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def get_settings() -> Tuple[Optional[Dict[str, List[dict]]], Optional[str]]:
        try:
            configs = await system_configurations_collection.find().to_list(length=None)
            normalized_configs = [normalize(conf) for conf in configs]
            grouped = SettingsService._group_settings(normalized_configs)
            return grouped, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def update_settings(settings: Dict[str, Any]) -> Tuple[Optional[Dict[str, List[dict]]], Optional[str]]:
        try:
            for key, value in settings.items():
                if key.endswith("_is_public"):
                    actual_key = key.replace("_is_public", "")
                    existing = await system_configurations_collection.find_one({"key": actual_key})
                    if existing:
                        await system_configurations_collection.update_one(
                            {"key": actual_key},
                            {"$set": {"is_public": value, "updated_at": datetime.utcnow()}},
                        )
                else:
                    existing = await system_configurations_collection.find_one({"key": key})
                    if existing:
                        await system_configurations_collection.update_one(
                            {"key": key},
                            {"$set": {"value": value, "updated_at": datetime.utcnow()}},
                        )

            return await SettingsService.get_settings()
        except Exception as e:
            traceback.print_exc()
            return None, str(e)
