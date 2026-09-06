import json
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime
from bson import ObjectId
from fastapi import UploadFile
from app.database import blogs_collection
from app.models import BlogCreate, BlogUpdate
from app.helper.file_handler import file_handler
from app.utils import normalize
import traceback


class BlogService:

    @staticmethod
    def _parse_tags(tags: Any) -> Optional[List[str]]:
        if tags is None:
            return None
        if isinstance(tags, list):
            return tags
        if isinstance(tags, str):
            tags_str = tags.strip()
            if not tags_str:
                return []
            try:
                parsed = json.loads(tags_str)
                return parsed if isinstance(parsed, list) else [tags_str]
            except Exception:
                return [t.strip() for t in tags_str.split(",") if t.strip()]
        return []

    @staticmethod
    async def create(
        title: str,
        slug: str,
        excerpt: str,
        content: str,
        category: str,
        tags: Optional[Union[str, List[str]]] = "[]",
        is_published: bool = True,
        cover_image: Optional[UploadFile] = None
    ) -> Tuple[Optional[dict], Optional[str]]:
        try:
            image_url = None
            if cover_image and cover_image.filename:
                uploaded = await file_handler.upload_file(cover_image, subfolder="blogs")
                image_url = uploaded["url"]

            parsed_tags = BlogService._parse_tags(tags) or []

            blog_data = BlogCreate(
                title=title,
                slug=slug,
                excerpt=excerpt,
                content=content,
                category=category,
                tags=parsed_tags,
                is_published=is_published,
                cover_image=image_url
            )

            data = blog_data.dict()
            data["deleted"] = False
            data["is_deleted"] = False
            data["deleted_at"] = None
            data["created_at"] = datetime.utcnow()

            result = await blogs_collection.insert_one(data)
            data["id"] = str(result.inserted_id)

            return normalize(data), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def list(
        page: int = 1,
        limit: int = 10,
        search: Optional[str] = None
    ) -> Tuple[Optional[List[dict]], Optional[dict], Optional[str]]:
        try:
            query = {
                "deleted": {"$ne": True},
                "is_deleted": {"$ne": True}
            }
            if search:
                query["title"] = {"$regex": search, "$options": "i"}

            total = await blogs_collection.count_documents(query)
            cursor = (
                blogs_collection.find(query)
                .sort("created_at", -1)
                .skip((page - 1) * limit)
                .limit(limit)
            )
            blogs_list = await cursor.to_list(length=limit)
            data = [normalize(b) for b in blogs_list]

            total_pages = (total + limit - 1) // limit if limit > 0 else 0
            meta = {
                "current_page": page,
                "total_pages": total_pages,
                "total_items": total,
                "limit": limit
            }

            return data, meta, None
        except Exception as e:
            traceback.print_exc()
            return None, None, str(e)

    @staticmethod
    async def get(blog_id: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            query = {
                "deleted": {"$ne": True},
                "is_deleted": {"$ne": True}
            }
            if ObjectId.is_valid(blog_id):
                query["_id"] = ObjectId(blog_id)
            else:
                query["slug"] = blog_id

            blog = await blogs_collection.find_one(query)
            if not blog:
                return None, "Blog post not found"

            blog_norm = normalize(blog)

            # Recommendations Logic
            recommendations = []
            rec_filters = []
            if blog_norm.get("category"):
                rec_filters.append({"category": blog_norm["category"]})

            if blog_norm.get("tags") and isinstance(blog_norm["tags"], list) and len(blog_norm["tags"]) > 0:
                rec_filters.append({"tags": {"$in": blog_norm["tags"]}})

            if rec_filters:
                rec_query = {
                    "deleted": {"$ne": True},
                    "is_deleted": {"$ne": True},
                    "_id": {"$ne": ObjectId(blog_norm["id"])},
                    "$or": rec_filters
                }
                cursor = blogs_collection.find(rec_query).sort("created_at", -1).limit(3)
                recs = await cursor.to_list(length=3)
                recommendations = [normalize(r) for r in recs]

            blog_norm["recommendations"] = recommendations
            return blog_norm, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def update(
        blog_id: str,
        title: Optional[str] = None,
        slug: Optional[str] = None,
        excerpt: Optional[str] = None,
        content: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[Union[str, List[str]]] = None,
        is_published: Optional[bool] = None,
        cover_image: Optional[UploadFile] = None
    ) -> Tuple[Optional[dict], Optional[str]]:
        try:
            image_url = None
            if cover_image and cover_image.filename:
                uploaded = await file_handler.upload_file(cover_image, subfolder="blogs")
                image_url = uploaded["url"]

            update_fields = {}
            if title is not None:
                update_fields["title"] = title
            if slug is not None:
                update_fields["slug"] = slug
            if excerpt is not None:
                update_fields["excerpt"] = excerpt
            if content is not None:
                update_fields["content"] = content
            if category is not None:
                update_fields["category"] = category
            if is_published is not None:
                update_fields["is_published"] = is_published
            if image_url is not None:
                update_fields["cover_image"] = image_url
            if tags is not None:
                update_fields["tags"] = BlogService._parse_tags(tags)

            blog_update_data = BlogUpdate(**update_fields)
            update_data = {k: v for k, v in blog_update_data.dict().items() if v is not None}

            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                query = {
                    "_id": ObjectId(blog_id) if ObjectId.is_valid(blog_id) else None,
                    "deleted": {"$ne": True},
                    "is_deleted": {"$ne": True}
                }
                if query["_id"] is None:
                    query = {"slug": blog_id, "deleted": {"$ne": True}, "is_deleted": {"$ne": True}}

                result = await blogs_collection.update_one(query, {"$set": update_data})
                if result.matched_count == 0:
                    return None, "Blog post not found"

            return await BlogService.get(blog_id)
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def delete(blog_id: str) -> Tuple[bool, Optional[str]]:
        try:
            query = {
                "deleted": {"$ne": True},
                "is_deleted": {"$ne": True}
            }
            if ObjectId.is_valid(blog_id):
                query["_id"] = ObjectId(blog_id)
            else:
                query["slug"] = blog_id

            result = await blogs_collection.update_one(
                query,
                {"$set": {"deleted": True, "is_deleted": True, "deleted_at": datetime.utcnow()}}
            )
            if result.matched_count == 0:
                return False, "Blog post not found"

            return True, None
        except Exception as e:
            traceback.print_exc()
            return False, str(e)
