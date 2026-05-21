import pytest

from backend.agents.fit_scorer import score_fit


def test_full_match():
    profile = {"skills": ["python", "react", "postgresql"]}
    jd = {"keywords": ["python", "react", "postgresql"]}
    assert score_fit(profile, jd) == 100.0


def test_partial_match():
    profile = {"skills": ["python", "react"]}
    jd = {"keywords": ["python", "react", "postgresql"]}
    score = score_fit(profile, jd)
    assert score == pytest.approx(66.67, rel=0.01)


def test_no_match():
    profile = {"skills": ["java"]}
    jd = {"keywords": ["python", "react"]}
    assert score_fit(profile, jd) == 0.0


def test_empty_jd_keywords():
    profile = {"skills": ["python"]}
    jd = {"keywords": []}
    assert score_fit(profile, jd) == 0.0


def test_empty_profile_skills():
    profile = {"skills": []}
    jd = {"keywords": ["python"]}
    assert score_fit(profile, jd) == 0.0


def test_case_insensitive():
    profile = {"skills": ["Python", "React"]}
    jd = {"keywords": ["python", "react"]}
    assert score_fit(profile, jd) == 100.0
