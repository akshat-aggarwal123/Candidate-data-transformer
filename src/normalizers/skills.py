"""Skill name canonicalization — maps aliases to a single canonical form."""

# Maps lowercase aliases → canonical display name
_SKILL_ALIASES: dict[str, str] = {
    # Python ecosystem
    "python": "Python", "py": "Python",
    "django": "Django", "flask": "Flask", "fastapi": "FastAPI",
    "pandas": "Pandas", "numpy": "NumPy", "numpy/pandas": "NumPy",
    "scikit-learn": "scikit-learn", "sklearn": "scikit-learn",
    "pytorch": "PyTorch", "torch": "PyTorch",
    "tensorflow": "TensorFlow", "tf": "TensorFlow",
    "keras": "Keras",

    # JavaScript / Web
    "javascript": "JavaScript", "js": "JavaScript", "es6": "JavaScript",
    "typescript": "TypeScript", "ts": "TypeScript",
    "node.js": "Node.js", "nodejs": "Node.js", "node": "Node.js",
    "react": "React", "react.js": "React", "reactjs": "React",
    "vue": "Vue.js", "vue.js": "Vue.js", "vuejs": "Vue.js",
    "angular": "Angular", "angularjs": "Angular",
    "next.js": "Next.js", "nextjs": "Next.js",
    "html": "HTML", "html5": "HTML",
    "css": "CSS", "css3": "CSS", "scss": "SCSS", "sass": "SCSS",

    # Backend / systems
    "java": "Java", "spring": "Spring Boot", "spring boot": "Spring Boot",
    "kotlin": "Kotlin", "scala": "Scala",
    "go": "Go", "golang": "Go",
    "rust": "Rust",
    "c++": "C++", "cpp": "C++",
    "c#": "C#", "csharp": "C#", ".net": ".NET", "dotnet": ".NET",
    "ruby": "Ruby", "ruby on rails": "Ruby on Rails", "rails": "Ruby on Rails",
    "php": "PHP", "laravel": "Laravel",

    # Data / ML
    "machine learning": "Machine Learning", "ml": "Machine Learning",
    "deep learning": "Deep Learning", "dl": "Deep Learning",
    "nlp": "NLP", "natural language processing": "NLP",
    "computer vision": "Computer Vision", "cv": "Computer Vision",
    "data science": "Data Science",
    "data engineering": "Data Engineering",
    "sql": "SQL", "mysql": "MySQL", "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL", "sqlite": "SQLite",
    "mongodb": "MongoDB", "mongo": "MongoDB",
    "redis": "Redis", "elasticsearch": "Elasticsearch",

    # Cloud / DevOps
    "aws": "AWS", "amazon web services": "AWS",
    "gcp": "GCP", "google cloud": "GCP", "google cloud platform": "GCP",
    "azure": "Azure", "microsoft azure": "Azure",
    "docker": "Docker", "kubernetes": "Kubernetes", "k8s": "Kubernetes",
    "terraform": "Terraform", "ansible": "Ansible",
    "ci/cd": "CI/CD", "jenkins": "Jenkins", "github actions": "GitHub Actions",

    # General
    "git": "Git", "github": "Git", "gitlab": "Git",
    "linux": "Linux", "unix": "Linux",
    "rest": "REST APIs", "rest api": "REST APIs", "restful": "REST APIs",
    "graphql": "GraphQL",
    "agile": "Agile", "scrum": "Scrum",
    "bash": "Bash", "shell": "Bash", "shell scripting": "Bash",
}


def canonicalize_skill(raw: str) -> str:
    """Return canonical skill name; falls back to title-cased original if not in map."""
    if not raw or not isinstance(raw, str):
        return raw
    cleaned = raw.strip()
    canonical = _SKILL_ALIASES.get(cleaned.lower())
    if canonical:
        return canonical
    # Not in map — return title-cased original rather than inventing
    return cleaned.strip()


def canonicalize_skills(raw_list: list) -> list:
    seen = {}
    for item in raw_list:
        if isinstance(item, str):
            name = canonicalize_skill(item)
        elif isinstance(item, dict):
            name = canonicalize_skill(item.get("name", ""))
        else:
            continue
        if name and name not in seen:
            seen[name] = True
    return list(seen.keys())
