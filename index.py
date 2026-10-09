import os
import re
import json
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

tickets_db = []
ticket_counter = 101

# Trigger-word overrides for emergency safety
EMERGENCY_KEYWORDS = [
    "fire", "spark", "shock", "flood", "leakage", "water leak", 
    "lock broken", "harassment", "gas leak", "ragging", "medical"
]

class ComplaintRequest(BaseModel):
    student_name: str
    student_email: str
    complaint_text: str

class StatusUpdateRequest(BaseModel):
    status: str

def check_emergency(text: str) -> bool:
    pattern = r"\b(" + "|".join(EMERGENCY_KEYWORDS) + r")\b"
    return bool(re.search(pattern, text, re.IGNORECASE))

@app.post("/api/complaints")
def submit_complaint(req: ComplaintRequest):
    global ticket_counter

    is_emergency = check_emergency(req.complaint_text)

    prompt = f"""
    Classify this student campus grievance.
    Complaint text: "{req.complaint_text}"

    Return strict JSON with:
    - "category": one of ["Hostel", "Academic", "Infrastructure"]
    - "department": one of ["Warden Office", "Dean Academic", "Estate Maintenance"]
    - "priority": one of ["Urgent", "Normal"]
    - "acknowledgement": a polite, courteous 2-sentence confirmation addressed to the student explaining their issue is logged and forwarded.
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        data = json.loads(response.text)
    except Exception:
        data = {
            "category": "Infrastructure",
            "department": "Estate Maintenance",
            "priority": "Normal",
            "acknowledgement": f"Thank you {req.student_name}. Your grievance has been recorded and directed to administration for review."
        }

    if is_emergency:
        data["priority"] = "Urgent"

    ticket = {
        "id": f"TICK-{ticket_counter}",
        "student_name": req.student_name,
        "student_email": req.student_email,
        "complaint_text": req.complaint_text,
        "category": data.get("category", "Infrastructure"),
        "department": data.get("department", "Estate Maintenance"),
        "priority": data.get("priority", "Normal"),
        "acknowledgement": data.get("acknowledgement"),
        "status": "Open",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    ticket_counter += 1
    tickets_db.insert(0, ticket)

    return ticket

@app.get("/api/complaints")
def get_complaints():
    return tickets_db

@app.patch("/api/complaints/{ticket_id}/status")
def update_status(ticket_id: str, req: StatusUpdateRequest):
    for ticket in tickets_db:
        if ticket["id"] == ticket_id:
            ticket["status"] = req.status
            return ticket
    return {"error": "Ticket not found"}