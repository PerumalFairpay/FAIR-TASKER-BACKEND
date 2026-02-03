from fastapi import APIRouter, HTTPException, Request, Depends, status
from app.database import db
from app.models import NDACreate, NDADocumentResponse, NDASignRequest, NDADocumentBase
from datetime import datetime, timedelta
import secrets
from fastapi.responses import JSONResponse
from jinja2 import Environment, FileSystemLoader
import os
import base64

router = APIRouter()

# Setup Jinja2 environment
templates_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
env = Environment(loader=FileSystemLoader(templates_dir))

def get_nda_collection():
    return db["nda_documents"]

@router.post("/", response_model=NDADocumentResponse)
async def create_nda_request(nda_data: NDACreate):
    collection = get_nda_collection()
    
    token = secrets.token_urlsafe(32)
    created_at = datetime.utcnow()
    expiry_at = created_at + timedelta(hours=1)
    
    new_nda = {
        "employee_name": nda_data.employee_name,
        "employee_role": nda_data.employee_role,
        "employee_address": nda_data.employee_address,
        "token": token,
        "created_at": created_at.isoformat(),
        "expiry_at": expiry_at.isoformat(),
        "status": "Pending",
        "signature_data": None
    }
    
    result = await collection.insert_one(new_nda)
    created_nda = await collection.find_one({"_id": result.inserted_id})
    
    return NDADocumentResponse(id=str(created_nda["_id"]), **created_nda)

@router.get("/{token}")
async def get_nda_details(token: str):
    collection = get_nda_collection()
    nda = await collection.find_one({"token": token})
    
    if not nda:
        raise HTTPException(status_code=404, detail="NDA not found")
        
    expiry_at = datetime.fromisoformat(nda["expiry_at"])
    if datetime.utcnow() > expiry_at:
         # Optionally allow viewing but mark as expired, or just 410.
         # For this request, let's return status so frontend handles it.
         pass

    # Render HTML using Jinja2
    template = env.get_template("nda_form.html")
    
    # Prepare context for template
    # Note: nda_form.html expects {{date}}, {{employee_name}}, {{employee_address}}
    # Converting date to a readable format
    readable_date = datetime.fromisoformat(nda["created_at"]).strftime("%B %d, %Y")
    
    html_content = template.render(
        date=readable_date,
        employee_name=nda["employee_name"],
        employee_role=nda.get("employee_role", ""),
        employee_address=nda["employee_address"],
        signature_data=nda.get("signature_data")
    )
    
    return JSONResponse(content={
        "html_content": html_content,
        "status": "Expired" if datetime.utcnow() > expiry_at else nda["status"],
        "employee_name": nda["employee_name"],
        "created_at": nda["created_at"]
    })

@router.post("/{token}/sign")
async def sign_nda(token: str, sign_request: NDASignRequest):
    collection = get_nda_collection()
    nda = await collection.find_one({"token": token})
    
    if not nda:
        raise HTTPException(status_code=404, detail="NDA not found")
        
    expiry_at = datetime.fromisoformat(nda["expiry_at"])
    if datetime.utcnow() > expiry_at:
        raise HTTPException(status_code=400, detail="NDA link has expired")
        
    if nda["status"] == "Signed":
        raise HTTPException(status_code=400, detail="NDA is already signed")

    # Update with signature
    new_values = {
            "status": "Signed",
            "signature_data": sign_request.signature_data,
            "signed_at": datetime.utcnow().isoformat()
        }
    
    await collection.update_one(
        {"token": token},
        {"$set": new_values}
    )
    
    # Re-render HTML with signature
    template = env.get_template("nda_form.html")
    readable_date = datetime.fromisoformat(nda["created_at"]).strftime("%B %d, %Y")
    
    html_content = template.render(
        date=readable_date,
        employee_name=nda["employee_name"],
        employee_role=nda.get("employee_role", ""),
        employee_address=nda["employee_address"],
        signature_data=sign_request.signature_data
    )
    
    return {
        "message": "NDA signed successfully",
        "html_content": html_content,
        "status": "Signed",
        "signature_data": sign_request.signature_data
    }
