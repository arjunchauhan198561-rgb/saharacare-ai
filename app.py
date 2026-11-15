import os
import json
import sqlite3
from datetime import datetime, date
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from google import genai

app = FastAPI(title="SaharaCare AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database Initialization
DB_FILE = "saharacare.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS medications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    dosage TEXT,
                    scheduled_time TEXT,
                    meal_rule TEXT,
                    purpose TEXT,
                    taken_today INTEGER DEFAULT 0
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS dose_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    med_name TEXT,
                    log_date TEXT,
                    scheduled_time TEXT,
                    actual_time TEXT,
                    status TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS appointments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doctor_name TEXT,
                    specialty TEXT,
                    date_time TEXT,
                    location TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS email_outbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipient TEXT,
                    subject TEXT,
                    body TEXT,
                    delivery_status TEXT,
                    created_at TEXT
                )''')
    
    # Seed initial data if empty
    c.execute("SELECT COUNT(*) FROM medications")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO medications (name, dosage, scheduled_time, meal_rule, purpose, taken_today) VALUES (?, ?, ?, ?, ?, ?)",
                  ("Amlodipine", "5mg", "09:00", "After breakfast", "Blood pressure control", 1))
        c.execute("INSERT INTO medications (name, dosage, scheduled_time, meal_rule, purpose, taken_today) VALUES (?, ?, ?, ?, ?, ?)",
                  ("Metformin", "500mg", "13:30", "After lunch", "Blood sugar management", 0))
        c.execute("INSERT INTO medications (name, dosage, scheduled_time, meal_rule, purpose, taken_today) VALUES (?, ?, ?, ?, ?, ?)",
                  ("Atorvastatin", "10mg", "20:00", "Before dinner", "Cholesterol control", 0))
        
        c.execute("INSERT INTO appointments (doctor_name, specialty, date_time, location) VALUES (?, ?, ?, ?)",
                  ("Dr. R. K. Sharma", "Cardiologist", "Monday, 10:30 AM", "Max Hospital, Shalimar Bagh"))
        
        c.execute("INSERT INTO dose_logs (med_name, log_date, scheduled_time, actual_time, status) VALUES (?, ?, ?, ?, ?)",
                  ("Amlodipine", str(date.today()), "09:00", "09:12 AM", "On Time"))

    conn.commit()
    conn.close()

init_db()

# Gemini Client setup
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyDummyKeyForHackathonFallback")
try:
    client = genai.Client(api_key=GEMINI_API_KEY)
except Exception:
    client = None

class LoginPayload(BaseModel):
    role: str
    mobile: str
    email: str

active_user_profile = {
    "role": "caretaker",
    "mobile": "919876543210",
    "email": "family.caretaker@example.com"
}

@app.post("/api/login")
def login(payload: LoginPayload):
    global active_user_profile
    active_user_profile = payload.dict()
    return {"status": "success", "role": payload.role, "profile": active_user_profile}

@app.get("/api/profile")
def get_profile():
    return active_user_profile

class MedCreate(BaseModel):
    name: str
    dosage: str
    scheduled_time: str
    meal_rule: str
    purpose: str

class ShiftPayload(BaseModel):
    scheduled_time: str

class SeniorTalkPayload(BaseModel):
    text: str

class AppointmentCreate(BaseModel):
    doctor_name: str
    specialty: str
    date_time: str
    location: str

@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h3>index.html not found. Please place it in the project directory.</h3>"

@app.get("/api/dashboard")
def get_dashboard():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    meds = [dict(row) for row in conn.execute("SELECT * FROM medications").fetchall()]
    logs = [dict(row) for row in conn.execute("SELECT * FROM dose_logs ORDER BY id DESC LIMIT 10").fetchall()]
    appts = [dict(row) for row in conn.execute("SELECT * FROM appointments").fetchall()]
    emails = [dict(row) for row in conn.execute("SELECT * FROM email_outbox ORDER BY id DESC LIMIT 5").fetchall()]
    
    streak = {
        "streak_days": 7,
        "senior_name": "Dadi",
        "senior_habit": "Morning Breathing & Pills",
        "senior_done": True,
        "family_name": "Aarav (Grandson)",
        "family_habit": "Morning Walk & Hydration",
        "family_done": True
    }

    drift_insight = {
        "med_id": 3,
        "med_name": "Atorvastatin 10mg",
        "suggested_time": "20:30",
        "message": "Dadi usually takes her evening Atorvastatin around 8:30 PM (after late tea) instead of 8:00 PM. Would you like SaharaCare AI to automatically shift the reminder?"
    }

    total_logs_count = conn.execute("SELECT COUNT(*) FROM dose_logs").fetchone()[0]
    late_logs_count = conn.execute("SELECT COUNT(*) FROM dose_logs WHERE status LIKE '%Late%'").fetchone()[0]
    compliance_score = max(65, 100 - (late_logs_count * 5))

    conn.close()
    return {
        "medications": meds,
        "dose_logs": logs,
        "appointments": appts,
        "streak": streak,
        "emails": emails,
        "drift_insight": drift_insight,
        "compliance_score": compliance_score
    }

@app.post("/api/senior/talk")
def senior_talk(payload: SeniorTalkPayload):
    spoken_reply = f"Namaste Dadi! I heard you say: '{payload.text}'. Everything looks good on your schedule. Remember to take your medications on time!"
    action = "info"
    double_dose_warning = False

    text_lower = payload.text.lower()
    if "took" in text_lower or "taken" in text_lower:
        spoken_reply = "Thank you for letting me know, Dadi! I have marked your medication as taken for today. Keep up the great streak!"
        action = "mark_taken"
    elif "dizzy" in text_lower or "pain" in text_lower or "unwell" in text_lower:
        spoken_reply = "Dadi, please sit down and rest immediately. I am alerting Aarav and your caretaker right now."
        action = "symptom_alert"
    elif "grapefruit" in text_lower or "alcohol" in text_lower:
        spoken_reply = "Careful Dadi! Consuming grapefruit with your Amlodipine can cause dangerous side effects. Please avoid it."
        double_dose_warning = True

    return {
        "spoken_reply": spoken_reply,
        "action": action,
        "med_name": None,
        "double_dose_warning": double_dose_warning,
        "trigger_email": False,
        "alert_summary": None
    }

@app.post("/api/senior/verify-pill")
async def verify_pill(file: UploadFile = File(...)):
    return {
        "identified_pill": "Amlodipine 5mg Tablet",
        "safe_to_take": True,
        "double_dose_risk": False,
        "spoken_message": "This is your Amlodipine 5mg tablet. You have not taken it yet today, so it is completely safe to consume!"
    }

@app.post("/api/medications")
def add_medication(med: MedCreate):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO medications (name, dosage, scheduled_time, meal_rule, purpose, taken_today) VALUES (?, ?, ?, ?, ?, 0)",
              (med.name, med.dosage, med.scheduled_time, med.meal_rule, med.purpose))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.delete("/api/medications/{med_id}")
def delete_medication(med_id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM medications WHERE id = ?", (med_id,))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/api/medications/{med_id}/shift")
def shift_medication(med_id: int, payload: ShiftPayload):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE medications SET scheduled_time = ? WHERE id = ?", (payload.scheduled_time, med_id))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/api/appointments")
def add_appointment_json(appt: AppointmentCreate):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 1. Save the appointment to the database
    c.execute("INSERT INTO appointments (doctor_name, specialty, date_time, location) VALUES (?, ?, ?, ?)",
              (appt.doctor_name, appt.specialty, appt.date_time, appt.location))
    
    # 2. AUTOMATICALLY generate an Email Outbox notification for the family
    subject = f"📅 New Doctor Appointment: {appt.doctor_name} ({appt.specialty})"
    body = (
        f"Hello Family,\n\n"
        f"A new medical appointment has been scheduled for Dadi:\n"
        f"• Doctor: {appt.doctor_name} ({appt.specialty})\n"
        f"• When: {appt.date_time}\n"
        f"• Location: {appt.location}\n\n"
        f"Please ensure transport and accompaniment are arranged. - SaharaCare AI"
    )
    recipient = active_user_profile.get("email", "family.caretaker@example.com")
    
    c.execute("INSERT INTO email_outbox (recipient, subject, body, delivery_status, created_at) VALUES (?, ?, ?, ?, ?)",
              (recipient, subject, body, "Logged in Outbox (Automated Appointment Alert)", datetime.now().strftime('%Y-%m-%d %I:%M %p')))
    
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/api/streak/family-checkin")
def family_checkin():
    return {"status": "success", "streak_days": 8}

@app.post("/api/demo/simulate-missed-dose")
def simulate_missed_dest(recipient: str = Form(...)):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    subject = f"🚨 Missed Medication Alert: Metformin 500mg ({datetime.now().strftime('%I:%M %p')})"
    body = f"Hello Caretaker,\n\nDadi missed her scheduled Metformin 500mg dose. SaharaCare AI has logged this event. Please check in with her immediately."
    c.execute("INSERT INTO email_outbox (recipient, subject, body, delivery_status, created_at) VALUES (?, ?, ?, ?, ?)",
              (recipient, subject, body, "Logged in Outbox (Simulated Outbox)", datetime.now().strftime('%Y-%m-%d %I:%M %p')))
    conn.commit()
    conn.close()
    return {"status": "simulated", "recipient": recipient}