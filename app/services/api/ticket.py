from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId
from app.database import tickets_collection, ticket_messages_collection, users_collection
from app.models import TicketCreate, TicketUpdate
from app.utils import normalize
import traceback


class TicketService:

    @staticmethod
    async def _generate_ticket_number() -> str:
        """Generates a sequential human-readable ticket number like TCK-1001"""
        try:
            count = await tickets_collection.count_documents({})
            return f"TCK-{1001 + count}"
        except Exception:
            return f"TCK-{int(datetime.utcnow().timestamp())}"

    @staticmethod
    async def _attach_user_info(data: dict, user_fields: List[str] = ["requester_id", "assigned_to"]) -> dict:
        """Helper to attach user details for given ID fields"""
        for field in user_fields:
            uid = data.get(field)
            target_key = "requester" if field == "requester_id" else "assignee"
            if uid and ObjectId.is_valid(uid):
                u = await users_collection.find_one({"_id": ObjectId(uid), "is_deleted": {"$ne": True}})
                if u:
                    data[target_key] = {
                        "id": str(u["_id"]),
                        "name": u.get("name") or u.get("username") or "",
                        "email": u.get("email"),
                        "role": u.get("role"),
                        "profile_picture": u.get("profile_picture")
                    }
                else:
                    data[target_key] = None
            else:
                data[target_key] = None
        return data

    @staticmethod
    async def create(ticket_in: TicketCreate) -> Tuple[Optional[dict], Optional[str]]:
        try:
            ticket_data = ticket_in.dict()
            ticket_data["ticket_number"] = await TicketService._generate_ticket_number()
            ticket_data["is_deleted"] = False
            ticket_data["deleted_at"] = None
            ticket_data["created_at"] = datetime.utcnow()
            ticket_data["updated_at"] = datetime.utcnow()

            result = await tickets_collection.insert_one(ticket_data)
            ticket_id = str(result.inserted_id)

            new_ticket, err = await TicketService.get(ticket_id)
            if err:
                return None, err

            return new_ticket, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def list(
        search: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        category: Optional[str] = None,
        requester_id: Optional[str] = None,
        assigned_to: Optional[str] = None,
        page: int = 1,
        limit: int = 50
    ) -> Tuple[Optional[List[dict]], Optional[dict], Optional[str]]:
        try:
            query: Dict[str, Any] = {"is_deleted": {"$ne": True}}

            if search:
                query["$or"] = [
                    {"ticket_number": {"$regex": search, "$options": "i"}},
                    {"title": {"$regex": search, "$options": "i"}},
                    {"description": {"$regex": search, "$options": "i"}}
                ]

            if status:
                query["status"] = status
            if priority:
                query["priority"] = priority
            if category:
                query["category"] = category
            if requester_id:
                query["requester_id"] = requester_id
            if assigned_to:
                query["assigned_to"] = assigned_to

            skip = max(0, (page - 1) * limit)

            total_items = await tickets_collection.count_documents(query)
            tickets_raw = await tickets_collection.find(query).sort("created_at", -1).skip(skip).limit(limit).to_list(length=None)

            result = []
            for t in tickets_raw:
                ticket = normalize(t)
                ticket = await TicketService._attach_user_info(ticket, ["requester_id", "assigned_to"])

                # Attach message count
                msg_count = await ticket_messages_collection.count_documents({
                    "ticket_id": ticket["id"],
                    "is_deleted": {"$ne": True}
                })
                ticket["messages_count"] = msg_count
                result.append(ticket)

            meta = {
                "page": page,
                "limit": limit,
                "total_items": total_items,
                "total_pages": (total_items + limit - 1) // limit if limit > 0 else 1
            }

            return result, meta, None
        except Exception as e:
            traceback.print_exc()
            return None, None, str(e)

    @staticmethod
    async def get(ticket_id: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(ticket_id):
                return None, "Invalid ticket ID"

            ticket_raw = await tickets_collection.find_one({
                "_id": ObjectId(ticket_id),
                "is_deleted": {"$ne": True}
            })
            if not ticket_raw:
                return None, "Ticket not found"

            ticket = normalize(ticket_raw)
            ticket = await TicketService._attach_user_info(ticket, ["requester_id", "assigned_to"])

            # Retrieve discussion messages
            messages_raw = await ticket_messages_collection.find({
                "ticket_id": ticket["id"],
                "is_deleted": {"$ne": True}
            }).sort("created_at", 1).to_list(length=None)

            messages = []
            for m in messages_raw:
                msg = normalize(m)
                sender_id = msg.get("sender_id")
                if sender_id and ObjectId.is_valid(sender_id):
                    u = await users_collection.find_one({"_id": ObjectId(sender_id), "is_deleted": {"$ne": True}})
                    if u:
                        msg["sender"] = {
                            "id": str(u["_id"]),
                            "name": u.get("name") or u.get("username") or "",
                            "email": u.get("email"),
                            "role": u.get("role"),
                            "profile_picture": u.get("profile_picture")
                        }
                messages.append(msg)

            ticket["messages"] = messages
            return ticket, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def update(ticket_id: str, ticket_in: TicketUpdate) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(ticket_id):
                return None, "Invalid ticket ID"

            existing = await tickets_collection.find_one({
                "_id": ObjectId(ticket_id),
                "is_deleted": {"$ne": True}
            })
            if not existing:
                return None, "Ticket not found"

            update_data = {k: v for k, v in ticket_in.dict().items() if v is not None}
            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                if "status" in update_data and update_data["status"] in ["Resolved", "Closed"]:
                    update_data["resolved_at"] = datetime.utcnow()

                await tickets_collection.update_one(
                    {"_id": ObjectId(ticket_id)},
                    {"$set": update_data}
                )

            updated_ticket, err = await TicketService.get(ticket_id)
            if err:
                return None, err

            return updated_ticket, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def add_message(
        ticket_id: str,
        sender_id: str,
        message: str,
        attachments: Optional[List[dict]] = None
    ) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(ticket_id):
                return None, "Invalid ticket ID"

            ticket = await tickets_collection.find_one({
                "_id": ObjectId(ticket_id),
                "is_deleted": {"$ne": True}
            })
            if not ticket:
                return None, "Ticket not found"

            msg_data = {
                "ticket_id": ticket_id,
                "sender_id": sender_id,
                "message": message,
                "attachments": attachments or [],
                "is_deleted": False,
                "created_at": datetime.utcnow()
            }

            result = await ticket_messages_collection.insert_one(msg_data)
            msg_id = str(result.inserted_id)

            # Touch ticket updated_at
            await tickets_collection.update_one(
                {"_id": ObjectId(ticket_id)},
                {"$set": {"updated_at": datetime.utcnow()}}
            )

            created_msg = normalize(await ticket_messages_collection.find_one({"_id": ObjectId(msg_id)}))
            if sender_id and ObjectId.is_valid(sender_id):
                u = await users_collection.find_one({"_id": ObjectId(sender_id), "is_deleted": {"$ne": True}})
                if u:
                    created_msg["sender"] = {
                        "id": str(u["_id"]),
                        "name": u.get("name") or u.get("username") or "",
                        "email": u.get("email"),
                        "role": u.get("role"),
                        "profile_picture": u.get("profile_picture")
                    }

            return created_msg, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def delete(ticket_id: str) -> Tuple[bool, Optional[str]]:
        try:
            if not ObjectId.is_valid(ticket_id):
                return False, "Invalid ticket ID"

            result = await tickets_collection.update_one(
                {"_id": ObjectId(ticket_id), "is_deleted": {"$ne": True}},
                {"$set": {"is_deleted": True, "deleted_at": datetime.utcnow()}}
            )
            if result.matched_count == 0:
                return False, "Ticket not found"

            return True, None
        except Exception as e:
            traceback.print_exc()
            return False, str(e)
