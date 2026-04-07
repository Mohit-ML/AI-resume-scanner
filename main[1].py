from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.responses import JSONResponse
import pdfplumber
import re
import io
import os

app = FastAPI(title="AI Resume Scanner")

os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

SKILLS_DB = {
    "programming": ["python", "javascript", "typescript", "java", "c++", "c#", "go", "rust", "php", "ruby", "swift", "kotlin", "scala", "r", "matlab"],
    "web": ["react", "vue", "angular", "html", "css", "sass", "nextjs", "nuxt", "svelte", "jquery", "bootstrap", "tailwind", "webpack", "vite"],
    "backend": ["fastapi", "django", "flask", "express", "spring", "laravel", "rails", "nodejs", "graphql", "rest", "api", "microservices"],
    "database": ["sql", "mysql", "postgresql", "mongodb", "redis", "elasticsearch", "sqlite", "oracle", "dynamodb", "firebase", "cassandra"],
    "cloud": ["aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ansible", "jenkins", "ci/cd", "devops", "linux", "nginx"],
    "ml_ai": ["machine learning", "deep learning", "tensorflow", "pytorch", "scikit-learn", "pandas", "numpy", "nlp", "computer vision", "llm", "openai", "huggingface"],
    "tools": ["git", "github", "jira", "agile", "scrum", "figma", "postman", "vs code", "linux", "bash", "powershell"],
    "soft": ["leadership", "communication", "teamwork", "problem solving", "project management", "mentoring", "collaboration", "analytical"]
}

def extract_text_from_pdf(file_bytes: bytes) -> str:
    text = ""
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text.strip()

def extract_skills(text: str) -> dict:
    text_lower = text.lower()
    found = {}
    for category, skills in SKILLS_DB.items():
        matched = [s for s in skills if re.search(r'\b' + re.escape(s) + r'\b', text_lower)]
        if matched:
            found[category] = matched
    return found

def extract_contact_info(text: str) -> dict:
    email = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    phone = re.findall(r'[\+\(]?[1-9][0-9 .\-\(\)]{7,}[0-9]', text)
    linkedin = re.findall(r'linkedin\.com/in/[\w\-]+', text, re.I)
    github = re.findall(r'github\.com/[\w\-]+', text, re.I)
    return {
        "email": email[0] if email else None,
        "phone": phone[0] if phone else None,
        "linkedin": linkedin[0] if linkedin else None,
        "github": github[0] if github else None
    }

def extract_education(text: str) -> list:
    degrees = re.findall(r'(b\.?tech|m\.?tech|b\.?e|m\.?e|b\.?sc|m\.?sc|phd|bachelor|master|mba|bca|mca|b\.?com|m\.?com)[^\n,]*', text, re.I)
    return list(set([d.strip() for d in degrees[:5]]))

def extract_experience_years(text: str) -> str:
    patterns = [
        r'(\d+)\+?\s*years?\s+of\s+experience',
        r'(\d+)\+?\s*years?\s+experience',
        r'experience\s+of\s+(\d+)\+?\s*years?'
    ]
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            return m.group(1) + " years"
    return "Not specified"

def calculate_match_score(resume_skills: dict, job_description: str) -> dict:
    if not job_description.strip():
        return {"score": 0, "matched": [], "missing": [], "breakdown": {}}

    jd_lower = job_description.lower()
    all_resume_skills = [s for skills in resume_skills.values() for s in skills]
    
    jd_required = []
    for category, skills in SKILLS_DB.items():
        for skill in skills:
            if re.search(r'\b' + re.escape(skill) + r'\b', jd_lower):
                jd_required.append(skill)

    if not jd_required:
        return {"score": 0, "matched": [], "missing": [], "breakdown": {}}

    matched = [s for s in jd_required if s in all_resume_skills]
    missing = [s for s in jd_required if s not in all_resume_skills]
    
    score = round((len(matched) / len(jd_required)) * 100) if jd_required else 0

    breakdown = {}
    for category, skills in resume_skills.items():
        cat_required = [s for s in jd_required if s in SKILLS_DB.get(category, [])]
        cat_matched = [s for s in cat_required if s in skills]
        if cat_required:
            breakdown[category] = {
                "matched": len(cat_matched),
                "total": len(cat_required),
                "pct": round(len(cat_matched)/len(cat_required)*100)
            }

    return {
        "score": score,
        "matched": matched,
        "missing": missing[:15],
        "breakdown": breakdown
    }

def generate_suggestions(score: int, missing_skills: list, resume_skills: dict, experience: str) -> list:
    suggestions = []
    
    if score < 40:
        suggestions.append("⚠️ Low match score — consider tailoring your resume specifically for this role.")
    elif score < 70:
        suggestions.append("📈 Moderate match — a few targeted additions could significantly boost your score.")
    else:
        suggestions.append("✅ Strong match! Your profile aligns well with the job description.")

    if missing_skills:
        top = missing_skills[:5]
        suggestions.append(f"🎯 Consider adding these missing skills: {', '.join(top)}.")

    total_skills = sum(len(v) for v in resume_skills.values())
    if total_skills < 8:
        suggestions.append("📝 Your resume lists fewer skills than average — expand the skills section with relevant technologies.")
    
    if "soft" not in resume_skills:
        suggestions.append("🤝 Add soft skills (leadership, communication, teamwork) to strengthen your profile.")
    
    if experience == "Not specified":
        suggestions.append("📅 Mention total years of experience clearly at the top of your resume.")

    if len(resume_skills.get("programming", [])) == 0 and len(resume_skills.get("web", [])) == 0:
        suggestions.append("💻 No technical skills detected — ensure skills are listed clearly in a dedicated section.")

    return suggestions

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/analyze")
async def analyze_resume(
    resume: UploadFile = File(...),
    job_description: str = Form(default="")
):
    if not resume.filename.endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported.")
    
    content = await resume.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(400, "File too large. Max 5MB.")

    try:
        text = extract_text_from_pdf(content)
    except Exception as e:
        raise HTTPException(500, f"Failed to extract PDF text: {str(e)}")

    if not text:
        raise HTTPException(400, "Could not extract text. Ensure PDF is not scanned/image-only.")

    skills = extract_skills(text)
    contact = extract_contact_info(text)
    education = extract_education(text)
    experience = extract_experience_years(text)
    match = calculate_match_score(skills, job_description)
    suggestions = generate_suggestions(match["score"], match["missing"], skills, experience)

    word_count = len(text.split())
    
    return JSONResponse({
        "success": True,
        "filename": resume.filename,
        "word_count": word_count,
        "contact": contact,
        "education": education,
        "experience": experience,
        "skills": skills,
        "total_skills": sum(len(v) for v in skills.values()),
        "match": match,
        "suggestions": suggestions,
        "has_jd": bool(job_description.strip())
    })
