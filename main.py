from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from supabase import create_client, Client
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

app = FastAPI(title="GAG Quiz API")

@app.middleware("http")
async def add_csp_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = "default-src * 'unsafe-inline' 'unsafe-eval' data: blob:;"
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
security = HTTPBearer(auto_error=False)

class StartQuiz(BaseModel):
    email: str
    name: str

class SubmitResult(BaseModel):
    email: str
    name: str
    score: int
    correct: int
    wrong: int

class SubmitExtra(BaseModel):
    email: str
    extra_score: int

class AdminLogin(BaseModel):
    password: str

# ===== PAGES =====
@app.get("/")
def index():
    content = open("index.html", "r", encoding="utf-8").read()
    return HTMLResponse(content=content)

@app.get("/admin")
def admin():
    content = open("admin.html", "r", encoding="utf-8").read()
    return HTMLResponse(content=content)

@app.get("/eksorular")
def eksorular():
    content = open("eksorular.html", "r", encoding="utf-8").read()
    return HTMLResponse(content=content)

@app.get("/logo")
def logo():
    if os.path.exists("logo.png"):
        return FileResponse("logo.png", media_type="image/png")
    raise HTTPException(status_code=404)

# ===== QUIZ API =====
@app.post("/api/start")
def start_quiz(data: StartQuiz):
    try:
        existing = supabase.table("participants").select("*").eq("email", data.email).execute()
        if existing.data:
            return {"ok": True, "returning": True}
        supabase.table("participants").insert({
            "email": data.email,
            "name": data.name,
            "started_at": datetime.utcnow().isoformat()
        }).execute()
        return {"ok": True, "returning": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/submit")
def submit_result(data: SubmitResult):
    try:
        existing = supabase.table("results").select("*").eq("email", data.email).execute()
        payload = {
            "email": data.email,
            "name": data.name,
            "score": data.score,
            "correct": data.correct,
            "wrong": data.wrong,
            "submitted_at": datetime.utcnow().isoformat()
        }
        if existing.data:
            if data.score > existing.data[0]["score"]:
                supabase.table("results").update(payload).eq("email", data.email).execute()
            return {"ok": True}
        else:
            supabase.table("results").insert(payload).execute()
            return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/my-rank")
def get_my_rank(email: str):
    try:
        all_results = supabase.table("results").select("email, score").order("score", desc=True).execute()
        rank = next((i+1 for i, r in enumerate(all_results.data) if r["email"] == email), None)
        return {"rank": rank, "total": len(all_results.data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ===== EK SORULAR =====
@app.get("/api/check-user")
def check_user(email: str):
    try:
        result = supabase.table("results").select("email").eq("email", email).execute()
        if not result.data:
            return {"exists": False, "already_done": False}
        extra = supabase.table("extra_results").select("email").eq("email", email).execute()
        return {"exists": True, "already_done": len(extra.data) > 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/submit-extra")
def submit_extra(data: SubmitExtra):
    try:
        existing = supabase.table("extra_results").select("*").eq("email", data.email).execute()
        if existing.data:
            return {"ok": True, "msg": "Zaten tamamlandı"}
        supabase.table("extra_results").insert({
            "email": data.email,
            "extra_score": data.extra_score,
            "submitted_at": datetime.utcnow().isoformat()
        }).execute()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ===== ADMIN =====
@app.post("/api/admin/login")
def admin_login(data: AdminLogin):
    if data.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Yanlış şifre")
    return {"ok": True, "token": ADMIN_PASSWORD}

def verify_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials or credentials.credentials != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Yetkisiz")
    return True

@app.get("/api/admin/leaderboard")
def admin_leaderboard(_=Depends(verify_admin)):
    try:
        results = supabase.table("results").select("*").order("score", desc=True).execute()
        extras = supabase.table("extra_results").select("*").execute()
        extra_map = {e["email"]: e["extra_score"] for e in extras.data}
        
        enriched = []
        for r in results.data:
            extra = extra_map.get(r["email"])
            total = r["score"] + (extra or 0)
            enriched.append({**r, "extra_score": extra, "total_score": total})
        
        # toplam puana göre sırala
        enriched.sort(key=lambda x: x["total_score"], reverse=True)
        return {"ok": True, "data": enriched, "total": len(enriched)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/stats")
def admin_stats(_=Depends(verify_admin)):
    try:
        results = supabase.table("results").select("score, correct").execute()
        participants = supabase.table("participants").select("email").execute()
        scores = [r["score"] for r in results.data]
        avg_score = sum(scores) / len(scores) if scores else 0
        avg_correct = sum(r["correct"] for r in results.data) / len(results.data) if results.data else 0
        return {
            "ok": True,
            "total_participants": len(participants.data),
            "total_completed": len(results.data),
            "avg_score": round(avg_score, 1),
            "avg_correct": round(avg_correct, 1),
            "max_score": max(scores) if scores else 0,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/admin/result/{email}")
def delete_result(email: str, _=Depends(verify_admin)):
    try:
        supabase.table("results").delete().eq("email", email).execute()
        supabase.table("extra_results").delete().eq("email", email).execute()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
