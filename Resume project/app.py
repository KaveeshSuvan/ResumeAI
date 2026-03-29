"""
AI Resume Analyzer & Career Roadmap Generator — Flask API.
"""

import io
from typing import Any, List, Set, Tuple
from ai_engine import ask_ollama
from flask import Flask, jsonify, request
from flask_cors import CORS
from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError

from gap import analyze_gap
from job_recommender import top_jobs
from resume_improver import build_improved_resume
from roadmap import build_roadmap
from skill_extractor import extract_skills, extract_skills_ordered



app = Flask(__name__)
CORS(app)

@app.route("/", methods=["GET"])
def index() -> Tuple[str, int]:
    return "AI Resume Analyzer Backend Running", 200


def _extract_pdf_text(file_storage) -> str:
    """Read PDF from upload and return plain text."""
    raw = file_storage.read()
    reader = PdfReader(io.BytesIO(raw))
    parts: List[str] = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            parts.append(t)
    return "\n".join(parts).strip()


def extract_pdf_text(file):
    reader = PdfReader(file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text


def _parse_request():
    from flask import request

    if "resume_pdf" in request.files:
        file = request.files["resume_pdf"]
        resume_text = extract_pdf_text(file)
    else:
        data = request.get_json()
        resume_text = data.get("resume", "")

    job_desc = request.form.get("job_desc") or (request.json or {}).get("job_desc", "")

    return resume_text, job_desc


@app.route("/analyze", methods=["POST"])
def analyze() -> Any:
    try:
        resume_text, job_description = _parse_request()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if not resume_text.strip():
        return jsonify({"error": "Resume text is empty. Paste text or upload a PDF."}), 400

    resume_skills = extract_skills(resume_text)
    # Preserve JD order so gap "missing" and critical skills follow job description priority
    jd_skills = extract_skills_ordered(job_description) if job_description.strip() else []

    gap_result = analyze_gap(resume_skills, jd_skills)
    matched = gap_result["matched"]
    missing = gap_result["missing"]
    match_score = float(gap_result["score"])
    critical_missing = gap_result["critical_missing"]

    roadmap_text = ask_ollama(f"""
    Create a clear step-by-step learning roadmap.

    skills_to_learn: {missing}

    Rules:
- Numbered steps
- Short titles only
- No explanation
- Max 5 steps
""")
    roadmap_list = []
    for step in roadmap_text.split("\n"):
     step = step.strip().lstrip("0123456789. -")
     if step:
        roadmap_list.append({
            "text": step,
            "link": f"https://www.google.com/search?q={step.replace(' ', '+')}"
        })

    improved = ask_ollama(f"""
    Rewrite this resume professionally.

    Rules:
    - Clear sections
    - ATS-friendly
 - No extra explanation

Resume:
{resume_text}

Job Description:
{job_description}
""")


    # 🧠 AI Job Matching
    jobs_before = ask_ollama(f"""
    Analyze the resume below and suggest EXACTLY 3 job roles that are a good fit for the user.

    Rules:
    - Return ONLY job titles
    - One job title per line
    - No explanation

    Resume:
    {resume_text}
    """).split("\n")

    jobs_before = [j.strip() for j in jobs_before if j.strip()]

    jobs_after = ask_ollama(f"""
    Given this resume:
    {resume_text}

    If the user learns these skills:
    {missing}

    Suggest EXACTLY 3 better job roles.
    Rules:
- Only job titles
- One per line
- No explanation
    """).split("\n")
    


    jobs_after = [j.strip() for j in jobs_after if j.strip()]

    insight = ask_ollama(f"""
    Explain in 2 lines:
    - Why this resume matches or does not match the job.
    - No explanation.
    Resume: {resume_text}
    Job: {job_description}
    """)

    payload = {
    "skills": resume_skills,
    "match_score": match_score,
    "missing_skills": missing,
    "roadmap": roadmap_list,
    "improved_resume": improved,
    "insight": insight,
    "job_suggestions_before": jobs_before,
    "job_suggestions_after": jobs_after,
}
    return jsonify(payload), 200


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
