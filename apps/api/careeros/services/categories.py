"""Explainable, multi-label career tracks, based on role title rather than incidental JD words."""

import re

CATEGORIES = {
    "software": "Software / SDE",
    "backend": "Backend",
    "frontend": "Frontend",
    "fullstack": "Full-stack",
    "data": "AI / ML / Data",
    "cloud": "Cloud / DevOps / Platform",
    "security": "Cybersecurity",
    "qa": "QA / Test automation",
    "design": "Product Design / UI–UX",
    "ux_research": "UX Research",
    "design_engineering": "Design Engineering",
}
PATTERNS = {
    "software": r"\b(software|sde|developer)\b",
    "backend": r"\bback[ -]?end\b",
    "frontend": r"\bfront[ -]?end\b",
    "fullstack": r"\bfull[ -]?stack\b",
    "data": r"\b(data|machine learning|ai|ml|artificial intelligence)\b",
    "cloud": r"\b(cloud|devops|platform|site reliability|infrastructure)\b",
    "security": r"\b(security|cybersecurity|cyber security)\b",
    "qa": r"\b(qa|qae|quality assurance|test(?:ing)? engineer)\b",
    "design": r"\b(product design(?:er)?|ui[ /-]?ux|ux[ /-]?ui|ux design(?:er)?|ui design(?:er)?|interaction design(?:er)?|user experience|user interface)\b",
    "ux_research": r"\b(ux research(?:er)?|user research(?:er)?|user experience research(?:er)?)\b",
    "design_engineering": r"\b(design engineer(?:ing)?|ux engineer(?:ing)?|ui engineer(?:ing)?)\b",
}


def classify(title):
    labels = [key for key, pattern in PATTERNS.items() if re.search(pattern, title, re.I)]
    if "design_engineering" in labels and re.search(
        r"mechanical|electrical|hardware|civil|physical|silicon", title, re.I
    ):
        labels.remove("design_engineering")
    if "ux_research" in labels or "design_engineering" in labels:
        labels = list(dict.fromkeys(["design", *labels]))
    return labels


def normalized_role(title):
    labels = classify(title)
    for key, role in (
        ("ux_research", "UX Researcher"),
        ("design_engineering", "Design Engineer"),
        ("design", "Product Designer"),
        ("fullstack", "Full-Stack Engineer"),
        ("backend", "Backend Engineer"),
        ("frontend", "Frontend Engineer"),
    ):
        if key in labels:
            return role
    return "Software Engineer" if "software" in labels else title
