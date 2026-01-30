
from fastapi import APIRouter, Depends, HTTPException, status
from app.auth import get_current_user
from app.services.docusign_service import docusign_service
from app.crud.repository import Repository
from bson import ObjectId
import os
from datetime import datetime

router = APIRouter(prefix="/digital-signature", tags=["Digital Signature"])
repo = Repository()

@router.post("/send-nda")
async def send_nda(
    current_user: dict = Depends(get_current_user)
):
    try:
        # 1. Get complete employee data
        # The current_user is from 'users' collection. We need to find the corresponding 'employee' record.
        # Users are linked to Employees via 'employee_id' field (which stores the employee_no_id string).
        
        emp_no_id = current_user.get('employee_id')
        if not emp_no_id:
             # Fallback: Try finding by email if employee_id is missing (e.g., admin or old record)
             employee_data = await repo.employees.find_one({"email": current_user.get('email')})
        else:
             employee_data = await repo.employees.find_one({"employee_no_id": emp_no_id})
             
        if employee_data:
            # Normalize ObjectId to string 'id'
            from app.utils import normalize
            employee_data = normalize(employee_data)
        
        if not employee_data:
             raise HTTPException(status_code=404, detail="Employee details not found")
        
        # Ensure we have minimal fields
        if not employee_data.get('email'):
             raise HTTPException(status_code=400, detail="Employee email is missing")
        
        # 2. Call DocuSign Service
        # We need a return URL for the embedded signing session
        # This should point to the frontend page that handles the signing completion
        # Route is /digital-signature/nda, not /app/digital-signature/nda
        return_url = f"{os.getenv('APP_URL', 'http://localhost:3001')}/digital-signature/nda?event=signing_complete"
        
        signing_url, envelope_id = docusign_service.send_nda_for_embedded_signing(employee_data, return_url)
        
        # Store envelope_id in employee record
        await repo.employees.update_one(
            {"_id": ObjectId(employee_data['id'])},
            {"$set": {
                "nda_envelope_id": envelope_id,
                "nda_status": "sent",
                "nda_sent_at": datetime.utcnow()
            }}
        )

        return {"signing_url": signing_url}

    except Exception as e:
        print(f"Error in send_nda: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to initiate signing: {str(e)}"
        )

@router.post("/verify-nda")
async def verify_nda(
    current_user: dict = Depends(get_current_user)
):
    try:
        # Get employee data
        emp_no_id = current_user.get('employee_id')
        if not emp_no_id:
             employee_data = await repo.employees.find_one({"email": current_user.get('email')})
        else:
             employee_data = await repo.employees.find_one({"employee_no_id": emp_no_id})
             
        if not employee_data:
             raise HTTPException(status_code=404, detail="Employee not found")
        
        envelope_id = employee_data.get("nda_envelope_id")
        if not envelope_id:
            # If no envelope_id, check if already signed manually or legacy
            if employee_data.get("nda_status") == "signed":
                return {
                    "status": "signed", 
                    "document_url": employee_data.get("nda_document_url")
                }
            raise HTTPException(status_code=400, detail="No NDA signing process initiated")

        # Check status with DocuSign
        status_text = docusign_service.get_envelope_status(envelope_id)
        
        if status_text == "completed":
            # Download and Save Document
            document_data = docusign_service.get_envelope_document(envelope_id)
            # document_data is bytes
            
            from app.helper.file_handler import file_handler
            filename = f"NDA_{employee_data.get('name', 'Employee').replace(' ', '_')}_{envelope_id}.pdf"
            
            save_result = await file_handler.save_from_bytes(
                file_bytes=document_data,
                filename=filename
            )

            # Update DB
            await repo.employees.update_one(
                {"_id": employee_data["_id"]},
                {"$set": {
                    "nda_status": "signed",
                    "nda_signed_at": datetime.utcnow(),
                    "nda_document_url": save_result["url"]
                }}
            )
            
            return {
                "status": "signed",
                "document_url": save_result["url"]
            }
            
        return {"status": status_text}

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error in verify_nda: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
