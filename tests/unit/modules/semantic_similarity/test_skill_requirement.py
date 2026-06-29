import pytest
from src.modules.semantic_similarity.skill_requirement import (
    SkillRequirement,
    parse_requirements,
)

def test_parse_empty_input():
    # Input kosong menghasilkan hasil kosong
    assert parse_requirements([]) == []

def test_parse_single_group_single_skill():
    # Input satu grup dengan satu skill
    result = parse_requirements([["React"]])
    assert len(result) == 1
    assert result[0].skills == ["React"]
    assert result[0].is_disjunctive is False
    assert result[0].label == "React"

def test_parse_single_group_multiple_skills():
    # Input satu grup dengan beberapa skill (disjunctive/OR)
    result = parse_requirements([["MySQL", "PostgreSQL"]])
    assert len(result) == 1
    assert result[0].skills == ["MySQL", "PostgreSQL"]
    assert result[0].is_disjunctive is True
    assert result[0].label == "MySQL | PostgreSQL"

def test_parse_multiple_groups():
    # Input beberapa grup gabungan AND dan OR
    result = parse_requirements([["React"], ["MySQL", "PostgreSQL"]])
    assert len(result) == 2
    
    # Assert grup pertama
    assert result[0].skills == ["React"]
    assert result[0].is_disjunctive is False
    assert result[0].label == "React"
    
    # Assert grup kedua
    assert result[1].skills == ["MySQL", "PostgreSQL"]
    assert result[1].is_disjunctive is True
    assert result[1].label == "MySQL | PostgreSQL"

def test_parse_empty_strings_and_spaces():
    # Input berisi string kosong atau spasi harus diabaikan
    result = parse_requirements([[" "], ["", "  ", "Vue "], []])
    assert len(result) == 1
    # Hanya "Vue " yang valid, tapi di-strip menjadi "Vue"
    assert result[0].skills == ["Vue"]
    assert result[0].is_disjunctive is False
    assert result[0].label == "Vue"

def test_parse_handles_non_strings():
    # Memastikan tidak error jika ada tipe data non-string
    result = parse_requirements([[123, "React", None]])
    assert len(result) == 1
    assert result[0].skills == ["React"]

def test_skill_requirement_dataclass_properties():
    # Validasi inisiasi object secara langsung
    req = SkillRequirement(skills=["A", "B"], is_disjunctive=True)
    assert req.label == "A | B"
    
    req_single = SkillRequirement(skills=["C"])
    assert req_single.is_disjunctive is False
    assert req_single.label == "C"
