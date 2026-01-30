
from fastapi import APIRouter, Depends, HTTPException, status
from app.auth import get_current_user
from app.services.docusign_service import docusign_service
from app.crud.repository import Repository
from bson import ObjectId
import os

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
        
        signing_url = docusign_service.send_nda_for_embedded_signing(employee_data, return_url)
        
        return {"signing_url": signing_url}

    except Exception as e:
        print(f"Error in send_nda: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to initiate signing: {str(e)}"
        )
