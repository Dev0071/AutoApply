def score_fit(profile: dict, jd: dict) -> float:
    profile_skills = {s.lower() for s in profile.get("skills", [])}
    jd_keywords = {k.lower() for k in jd.get("keywords", [])}

    if not jd_keywords:
        return 0.0

    matched = profile_skills & jd_keywords
    return round(len(matched) / len(jd_keywords) * 100, 2)
