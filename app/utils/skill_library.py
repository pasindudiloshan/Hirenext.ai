# app/utils/skill_library.py

"""
Central Skill Library System

Purpose:
- Store categorized skills
- Provide flattened list for UI (datalist)
- Provide fast validation set
- Provide helper validation utilities
- Normalize and clean skills from form input
"""


# =====================================================
# 🟦 Categorized Skill Dictionary (Scalable)
# =====================================================

SKILL_LIBRARY = {
    "core_tech": [
        "Python", "Java", "JavaScript", "TypeScript", "C#", "C++", "PHP",
        "SQL", "MySQL", "PostgreSQL", "MongoDB",
        "Machine Learning", "Deep Learning", "NLP", "Data Analysis",
        "Flask", "Django", "FastAPI", "React", "Node.js",
        "Docker", "Kubernetes", "Git", "GitHub",
    ],

    "office_tools": [
        "Microsoft Excel",
        "Microsoft Word",
        "Microsoft PowerPoint",
    ],

    "hr_domain": [
        "Recruitment",
        "Onboarding",
        "Employee Relations",
        "HR Administration",
        "HRIS",
        "Labor Law",
        "Payroll",
        "Compliance",
        "Training",
        "Performance Management",
    ],

    "hr_systems": [
        "Workday",
        "PeopleSoft",
        "SAP SuccessFactors",
        "SAP",
    ]
}


# =====================================================
# 🟦 Flattened List (for UI suggestions)
# =====================================================

def _flatten_skills(skill_dict: dict) -> list:
    """Flatten categorized dictionary into unique sorted list."""
    skills = []
    for category in skill_dict.values():
        skills.extend(category)

    # Remove duplicates while preserving order
    seen = set()
    unique_skills = []
    for skill in skills:
        if skill not in seen:
            unique_skills.append(skill)
            seen.add(skill)

    return sorted(unique_skills)


ALL_SKILLS = _flatten_skills(SKILL_LIBRARY)


# =====================================================
# 🟦 Lowercase Set (Fast Validation)
# =====================================================

ALL_SKILLS_LOWER = {skill.lower() for skill in ALL_SKILLS}


# =====================================================
# 🟦 Utility: Parse Comma-Separated Skills
# =====================================================

def parse_skills(skill_string: str) -> list:
    """
    Convert comma-separated string into clean list.
    Example:
    "Python, Flask,  SQL  " → ["Python", "Flask", "SQL"]
    """
    if not skill_string:
        return []

    return [
        skill.strip()
        for skill in skill_string.split(",")
        if skill.strip()
    ]


# =====================================================
# 🟦 Utility: Normalize Skill (case-insensitive match)
# =====================================================

def normalize_skill(skill: str) -> str | None:
    """
    Normalize input skill to proper casing from library.
    Example:
    "python" → "Python"
    """
    if not skill:
        return None

    skill_lower = skill.strip().lower()

    for original in ALL_SKILLS:
        if original.lower() == skill_lower:
            return original

    return None


# =====================================================
# 🟦 Utility: Validate Skills
# =====================================================

def validate_skills(skill_string: str) -> tuple[list, list]:
    """
    Validate comma-separated skills.

    Returns:
        (valid_skills, invalid_skills)
    """

    parsed = parse_skills(skill_string)

    valid = []
    invalid = []

    for skill in parsed:
        normalized = normalize_skill(skill)

        if normalized:
            valid.append(normalized)
        else:
            invalid.append(skill)

    return valid, invalid


# =====================================================
# 🟦 Utility: Get Skills by Category
# =====================================================

def get_skills_by_category(category: str) -> list:
    """
    Return skills under a category.
    """
    return SKILL_LIBRARY.get(category, [])


# =====================================================
# 🟦 Utility: Get Category of Skill
# =====================================================

def get_skill_category(skill: str) -> str | None:
    """
    Find which category a skill belongs to.
    """
    skill_lower = skill.lower()

    for category, skills in SKILL_LIBRARY.items():
        for s in skills:
            if s.lower() == skill_lower:
                return category

    return None