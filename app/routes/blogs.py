from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse
from app.crud.repository import repository as repo
from app.models import BlogCreate, BlogUpdate
from app.helper.file_handler import file_handler
from typing import List, Optional
import json

from app.auth import verify_token

router = APIRouter(
    prefix="/blogs", tags=["blogs"], dependencies=[Depends(verify_token)]
)


@router.post("/create")
async def create_blog(
    title: str = Form(...),
    slug: str = Form(...),
    excerpt: str = Form(...),
    content: str = Form(...),
    category: str = Form(...),
    tags: Optional[str] = Form("[]"),
    is_published: bool = Form(True),
    cover_image: Optional[UploadFile] = File(None),
):
    try:
        image_url = None
        if cover_image:
            uploaded = await file_handler.upload_file(cover_image, subfolder="blogs")
            image_url = uploaded["url"]

        try:
            parsed_tags = json.loads(tags)
        except:
            parsed_tags = tags.split(",") if tags else []

        blog_data = BlogCreate(
            title=title,
            slug=slug,
            excerpt=excerpt,
            content=content,
            category=category,
            tags=parsed_tags,
            is_published=is_published,
            cover_image=image_url,
        )

        new_blog = await repo.create_blog(blog_data)
        return JSONResponse(
            status_code=201,
            content={
                "message": "Blog post created successfully",
                "success": True,
                "data": new_blog,
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to create blog: {str(e)}", "success": False},
        )


@router.get("/all")
async def get_blogs(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1),
    search: Optional[str] = None,
):
    try:
        result = await repo.get_blogs(page, limit, search)
        return JSONResponse(
            status_code=200,
            content={
                "message": "Blogs fetched successfully",
                "success": True,
                "data": result["data"],
                "meta": result["meta"],
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to fetch blogs: {str(e)}", "success": False},
        )


@router.get("/{blog_id}")
async def get_blog(blog_id: str):
    try:
        blog = await repo.get_blog(blog_id)
        if not blog:
            return JSONResponse(
                status_code=404,
                content={"message": "Blog post not found", "success": False},
            )
        return JSONResponse(
            status_code=200,
            content={
                "message": "Blog fetched successfully",
                "success": True,
                "data": blog,
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to fetch blog: {str(e)}", "success": False},
        )


@router.put("/update/{blog_id}")
async def update_blog(
    blog_id: str,
    title: Optional[str] = Form(None),
    slug: Optional[str] = Form(None),
    excerpt: Optional[str] = Form(None),
    content: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    is_published: Optional[bool] = Form(None),
    cover_image: Optional[UploadFile] = File(None),
):
    try:
        image_url = None
        if cover_image:
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
            try:
                update_fields["tags"] = json.loads(tags)
            except:
                update_fields["tags"] = tags.split(",") if tags else []

        blog_update_data = BlogUpdate(**update_fields)

        updated_blog = await repo.update_blog(blog_id, blog_update_data)
        if not updated_blog:
            return JSONResponse(
                status_code=404,
                content={"message": "Blog post not found", "success": False},
            )
        return JSONResponse(
            status_code=200,
            content={
                "message": "Blog updated successfully",
                "success": True,
                "data": updated_blog,
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to update blog: {str(e)}", "success": False},
        )


@router.delete("/delete/{blog_id}")
async def delete_blog(blog_id: str):
    try:
        success = await repo.delete_blog(blog_id)
        if not success:
            return JSONResponse(
                status_code=404,
                content={"message": "Blog post not found", "success": False},
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Blog deleted successfully", "success": True},
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to delete blog: {str(e)}", "success": False},
        )
