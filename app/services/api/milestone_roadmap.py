from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId
from app.database import milestones_roadmaps_collection
from app.models import MilestoneRoadmapCreate, MilestoneRoadmapUpdate
from app.utils import normalize
import traceback


class MilestoneRoadmapService:

    @staticmethod
    async def create(item_in: MilestoneRoadmapCreate) -> Tuple[Optional[dict], Optional[str]]:
        try:
            item_data = item_in.dict()
            item_data["is_deleted"] = False
            item_data["deleted_at"] = None
            item_data["created_at"] = datetime.utcnow()
            result = await milestones_roadmaps_collection.insert_one(item_data)
            item_data["id"] = str(result.inserted_id)
            return normalize(item_data), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def list(
        project_id: Optional[str] = None,
        assigned_to: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None
    ) -> Tuple[Optional[List[dict]], Optional[str]]:
        try:
            query = {"is_deleted": {"$ne": True}}
            if project_id:
                query["project_id"] = project_id
            if assigned_to:
                query["assigned_to"] = assigned_to
            if status:
                query["status"] = status
            if priority:
                query["priority"] = priority

            items = await milestones_roadmaps_collection.find(query).sort("created_at", -1).to_list(length=None)
            return [normalize(item) for item in items], None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def get(item_id: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(item_id):
                return None, "Invalid milestone/roadmap ID"

            item = await milestones_roadmaps_collection.find_one({
                "_id": ObjectId(item_id),
                "is_deleted": {"$ne": True}
            })
            if not item:
                return None, "Milestone/Roadmap item not found"

            return normalize(item), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def update(
        item_id: str,
        item_in: MilestoneRoadmapUpdate
    ) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(item_id):
                return None, "Invalid milestone/roadmap ID"

            existing = await milestones_roadmaps_collection.find_one({
                "_id": ObjectId(item_id),
                "is_deleted": {"$ne": True}
            })
            if not existing:
                return None, "Milestone/Roadmap item not found"

            update_data = {k: v for k, v in item_in.dict().items() if v is not None}
            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                await milestones_roadmaps_collection.update_one(
                    {"_id": ObjectId(item_id)}, {"$set": update_data}
                )

            updated = await milestones_roadmaps_collection.find_one({"_id": ObjectId(item_id)})
            return normalize(updated), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def delete(item_id: str) -> Tuple[bool, Optional[str]]:
        try:
            if not ObjectId.is_valid(item_id):
                return False, "Invalid milestone/roadmap ID"

            result = await milestones_roadmaps_collection.update_one(
                {"_id": ObjectId(item_id), "is_deleted": {"$ne": True}},
                {"$set": {"is_deleted": True, "deleted_at": datetime.utcnow()}}
            )
            if result.matched_count == 0:
                return False, "Milestone/Roadmap item not found"

            return True, None
        except Exception as e:
            traceback.print_exc()
            return False, str(e)
