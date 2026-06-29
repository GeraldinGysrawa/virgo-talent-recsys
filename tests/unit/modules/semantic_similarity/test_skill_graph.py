import pytest
from unittest.mock import MagicMock

from src.modules.semantic_similarity.skill_graph import SkillGraph, SkillNode


def mock_neo4j_driver(nodes=None, relations=None, empty_primary=False):
    """Membantu membuat mock neo4j.Driver dengan kembalian kustom."""
    if nodes is None:
        nodes = [
            {"uri": "padepokan79#React", "label": "React"},
            {"uri": "padepokan79#Frontend", "label": "Frontend"},
            {"uri": "padepokan79#IT", "label": "IT"}
        ]
    if relations is None:
        relations = [
            {"child_uri": "padepokan79#React", "parent_uri": "padepokan79#Frontend"},
            {"child_uri": "padepokan79#Frontend", "parent_uri": "padepokan79#IT"}
        ]
        
    driver = MagicMock()
    session = MagicMock()
    
    # Context manager setup for `with driver.session(...) as session:`
    driver.session.return_value.__enter__.return_value = session
    
    def session_run_side_effect(query, *args, **kwargs):
        if "CONTAINS \"padepokan79\"" in query:
            return [] if empty_primary else nodes
        elif "MATCH (s:owl__Class)" in query:  # Fallback query
            return nodes
        elif "[:rdfs__subClassOf]" in query:
            return relations
        return []
        
    session.run.side_effect = session_run_side_effect
    return driver


def test_skill_graph_load_success():
    # graph berhasil memuat node/class & relasi dari hasil mock Neo4j
    driver = mock_neo4j_driver()
    graph = SkillGraph(driver)
    
    # Pastikan node dimuat
    assert len(graph.all_uris()) == 3
    assert "padepokan79#React" in graph.all_uris()
    
    # Pastikan relasi parent-child dimuat
    react_node = graph.get_by_uri("padepokan79#React")
    assert react_node is not None
    assert "padepokan79#Frontend" in react_node.parents
    assert len(react_node.children) == 0
    
    frontend_node = graph.get_by_uri("padepokan79#Frontend")
    assert "padepokan79#React" in frontend_node.children
    assert "padepokan79#IT" in frontend_node.parents


def test_get_by_label():
    # get_by_label() mengembalikan URI/node yang benar sesuai label
    driver = mock_neo4j_driver()
    graph = SkillGraph(driver)
    
    node = graph.get_by_label("react")
    assert node is not None
    assert node.uri == "padepokan79#React"
    
    # Case insensitive check
    node2 = graph.get_by_label("REACT")
    assert node2 is not None
    assert node2.uri == "padepokan79#React"


def test_get_by_label_unknown():
    # edge case: URI tidak ditemukan mengembalikan hasil aman (None)
    driver = mock_neo4j_driver()
    graph = SkillGraph(driver)
    
    assert graph.get_by_label("Unknown") is None
    assert graph.get_by_uri("Unknown") is None


def test_subsumers_logic_and_caching():
    # subsumers() mengembalikan node itu sendiri dan semua ancestor sampai root
    driver = mock_neo4j_driver()
    graph = SkillGraph(driver)
    
    subs = graph.subsumers("padepokan79#React")
    assert len(subs) == 3
    assert "padepokan79#React" in subs
    assert "padepokan79#Frontend" in subs
    assert "padepokan79#IT" in subs
    
    # subsumers() menggunakan cache
    assert "padepokan79#React" in graph._ancestors_cache
    
    # Panggilan kedua harus mengembalikan objek yang sama dari cache (is, bukan sekadar ==)
    subs_cached = graph.subsumers("padepokan79#React")
    assert subs is subs_cached


def test_subsumers_unknown_uri():
    # edge case: Jika URI tidak dikenal, subsumers hanya mengembalikan uri itu sendiri
    driver = mock_neo4j_driver()
    graph = SkillGraph(driver)
    
    subs = graph.subsumers("unknown_uri")
    assert subs == frozenset(["unknown_uri"])


def test_fallback_query():
    # fallback query dijalankan jika query utama namespace padepokan79 tidak mengembalikan data
    fallback_nodes = [
        {"uri": "other#Vue", "label": "Vue"}
    ]
    driver = mock_neo4j_driver(nodes=fallback_nodes, empty_primary=True)
    graph = SkillGraph(driver)
    
    # Pastikan data tetap dimuat dari fallback
    assert len(graph.all_uris()) == 1
    assert "other#Vue" in graph.all_uris()
    
    # Verifikasi session.run dipanggil 3 kali: 1. Main query, 2. Fallback, 3. Relations
    session = driver.session.return_value.__enter__.return_value
    assert session.run.call_count == 3


def test_empty_label_and_uri_fallback():
    # edge case: handle node tanpa label dan node tanpa URI
    nodes = [
        {"uri": "padepokan79#NoLabel", "label": None},
        {"uri": None, "label": "NoURI"}
    ]
    driver = mock_neo4j_driver(nodes=nodes, relations=[])
    graph = SkillGraph(driver)
    
    # Node NoLabel mengambil bagian akhir uri
    node = graph.get_by_uri("padepokan79#NoLabel")
    assert node is not None
    assert node.label == "NoLabel"
    
    # Node NoURI dilewati (tidak disimpan)
    assert len(graph.all_uris()) == 1
