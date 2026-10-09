"""Conservative notice parser; proposals require human review before use as hard facts."""

import html
import re

from careeros.schemas import JobIn

SKILLS = [
    "Figma",
    "Framer",
    "Sketch",
    "Adobe XD",
    "Wireframing",
    "Prototyping",
    "User research",
    "Usability testing",
    "Interaction design",
    "Design systems",
    "Accessibility",
    "Typography",
    "Information architecture",
    "Python",
    "C++",
    "Java",
    "JavaScript",
    "TypeScript",
    "React",
    "Node.js",
    "FastAPI",
    "PostgreSQL",
    "SQL",
    "Docker",
    "AWS",
    "Kubernetes",
    "Git",
    "Testing",
    "DSA",
    "OOP",
    "Redis",
    "Linux",
]


def clean_html(text):
    text = html.unescape(html.unescape(text or ""))
    text = re.sub(r"</?(?:p|div|li|br|h[1-6])\b[^>]*>", "\n", text, flags=re.I)
    return re.sub(r"<[^>]*>", "", text).strip()


def parse_notice(text):
    text = clean_html(text)
    fields, req, provenance = {}, {}, {}
    for key, pattern in {
        "company_name": r"(?:company|organization)\s*[:\-]\s*([^\n]+)",
        "title": r"(?:role|position|job title)\s*[:\-]\s*([^\n]+)",
        "stipend": r"(?:stipend|salary)\s*[:\-]\s*([^\n]+)",
    }.items():
        m = re.search(r"^\s*" + pattern, text, re.I | re.M)
        if m and len(m.group(1)) <= {"company_name": 160, "title": 240, "stipend": 200}[key]:
            fields[key] = m.group(1).strip()
            provenance[key] = {"method": "rules", "confidence": 0.85, "source_text": m.group(0)}
    for key, pattern in {
        "minimum_cgpa": r"(?:minimum\s+)?(?:cgpa|gpa)\s*(?:required)?\s*[:>=\-]*\s*(\d{1,2}(?:\.\d+)?)",
        "minimum_experience": r"(\d+)\+?\s+years?\s+(?:of\s+)?experience",
    }.items():
        m = re.search(pattern, text, re.I)
        if m:
            req[key] = float(m.group(1))
            provenance[key] = {"method": "rules", "confidence": 0.85, "source_text": m.group(0)}
    m = re.search(
        r"(?:graduation|batch|graduating|graduates?)\s*(?:year|of|in)?\s*[:\-]?\s*((?:20\d{2})(?:\s*[,/\-]\s*20\d{2})*)",
        text,
        re.I,
    )
    if m:
        req["allowed_graduation_years"] = [int(x) for x in re.findall(r"20\d{2}", m.group(1))]
        provenance["allowed_graduation_years"] = {
            "method": "rules",
            "confidence": 0.8,
            "source_text": m.group(0),
        }
    m = re.search(r"(?:deadline|apply by)\s*:\s*(\d{4}-\d{2}-\d{2}(?:T[\d:]+Z)?)", text, re.I)
    if m:
        fields["application_deadline"] = m.group(1)
        provenance["application_deadline"] = {
            "method": "rules",
            "confidence": 0.9,
            "source_text": m.group(0),
        }
    m = re.search(r"(?:branch|branches)\s*:\s*([^\n]+)", text, re.I)
    if m:
        req["branch_requirements"] = [x.strip() for x in re.split(r"[,/]", m.group(1))]
        provenance["branch_requirements"] = {
            "method": "rules",
            "confidence": 0.8,
            "source_text": m.group(0),
        }
    for key, label in [("locations", "location"), ("selection_stages", "selection stages")]:
        m = re.search(rf"{label}\s*:\s*([^\n]+)", text, re.I)
        if m:
            fields[key] = [x.strip() for x in m.group(1).split(",")]
    required, preferred = set(), set()
    for sentence in re.split(r"[\n.;]", text):
        target = (
            preferred
            if re.search(r"preferred|nice.to.have|bonus|optional", sentence, re.I)
            else required
        )
        for skill in SKILLS:
            if re.search(r"(?<!\w)" + re.escape(skill) + r"(?!\w)", sentence, re.I):
                target.add(skill)
    result = JobIn(
        company_name=fields.pop("company_name", "Review company name"),
        title=fields.pop("title", "Review role title"),
        description=text,
        source="campus",
        requirements=req,
        required_skills=sorted(required),
        preferred_skills=sorted(preferred - required),
        provenance=provenance,
        **fields,
    )
    return {
        "job": result.model_dump(mode="json"),
        "warnings": [
            "Review extracted fields and dates before saving. Unrecognized requirements remain unknown.",
            "A date without a time is interpreted as 00:00 UTC; set the actual deadline and timezone.",
        ],
    }
