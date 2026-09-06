from fastapi import APIRouter, Depends, UploadFile, File, Form, Query
from app.services.api.blog import BlogService
from app.helper.response_helper import success_response, error_response
from typing import Optional
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
    data, error = await BlogService.create(
        title=title,
        slug=slug,
        excerpt=excerpt,
        content=content,
        category=category,
        tags=tags,
        is_published=is_published,
        cover_image=cover_image
    )
    if error:
        return error_response(message=f"Failed to create blog: {error}", status_code=500)
    return success_response(message="Blog post created successfully", data=data, status_code=201)


@router.get("/all")
async def get_blogs(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1),
    search: Optional[str] = None,
):
    data, meta, error = await BlogService.list(page=page, limit=limit, search=search)
    if error:
        return error_response(message=f"Failed to fetch blogs: {error}", status_code=500)
    return success_response(
        message="Blogs fetched successfully",
        data=data,
        meta=meta
    )


@router.get("/{blog_id}")
async def get_blog(blog_id: str):
    data, error = await BlogService.get(blog_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Blog fetched successfully", data=data)


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
    data, error = await BlogService.update(
        blog_id=blog_id,
        title=title,
        slug=slug,
        excerpt=excerpt,
        content=content,
        category=category,
        tags=tags,
        is_published=is_published,
        cover_image=cover_image
    )
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Blog updated successfully", data=data)


@router.delete("/delete/{blog_id}")
async def delete_blog(blog_id: str):
    success, error = await BlogService.delete(blog_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Blog deleted successfully", data=[])
