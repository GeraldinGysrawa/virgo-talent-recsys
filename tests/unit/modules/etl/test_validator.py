import pytest
from unittest.mock import MagicMock, patch

from src.modules.etl.validator import OntologyValidator, ValidationResult
from src.modules.etl.transformer import TalentRecord


@pytest.fixture
def dummy_record():
    return TalentRecord(
        nip="123",
        nama_lengkap="Dummy",
        pengalaman_tahun=1.0,
        concern_perbankan=False,
        jenis_penempatan=["Bandung"],
        skill_labels=["React.js"]
    )


@patch('src.modules.etl.validator.Graph')
@patch('src.modules.etl.validator.owl.World')
def test_validator_initialization(mock_world_cls, mock_graph_cls):
    # Memastikan file .ttl dimuat dan dictionary `_skill_label_map` terisi 
    # tanpa memuat file sungguhan
    mock_world = MagicMock()
    mock_world_cls.return_value = mock_world
    
    mock_graph = MagicMock()
    mock_graph.serialize.return_value = "<rdf:RDF></rdf:RDF>"
    mock_graph_cls.return_value = mock_graph
    
    mock_onto = MagicMock()
    cls1 = MagicMock()
    cls1.name = "react.js"
    cls1.label = ["React.js"]
    cls1.iri = "http://test/React.js"
    
    cls2 = MagicMock()
    cls2.name = "vue.js"
    cls2.label = ["Vue.js"]
    cls2.iri = "http://test/Vue.js"
    
    mock_onto.classes.return_value = [cls1, cls2]
    mock_world.get_ontology.return_value.load.return_value = mock_onto
    
    with patch('src.modules.etl.validator.Path.exists', return_value=True):
        validator = OntologyValidator("dummy.ttl")
    
    assert validator._onto == mock_onto
    assert "react.js" in validator._skill_label_map
    assert validator.get_skill_uri("React.js") == "http://test/React.js"


@patch('src.modules.etl.validator.sync_reasoner_hermit')
@patch('src.modules.etl.validator.OntologyValidator._load_ontology')
@patch('src.modules.etl.validator.OntologyValidator._load_turtle_ontology')
@patch('src.modules.etl.validator.owl.World')
def test_validator_check_fields(mock_world, mock_load_ttl, mock_load_onto, mock_reasoner, dummy_record):
    # Menguji logika _check_nip dan _check_placement
    validator = OntologyValidator("dummy.ttl")
    
    # Test valid
    res1 = validator.validate(dummy_record)
    assert res1.is_valid is True
    
    # Test invalid NIP
    dummy_record.nip = "   "
    res2 = validator.validate(dummy_record)
    assert res2.is_valid is False
    assert any("NIP kosong" in e for e in res2.errors)
    
    # Test invalid placement
    dummy_record.nip = "123"
    dummy_record.jenis_penempatan = ["Planet Mars"]
    res3 = validator.validate(dummy_record)
    assert res3.is_valid is False
    assert any("tidak dikenal" in e for e in res3.errors)


@patch('src.modules.etl.validator.sync_reasoner_hermit')
@patch('src.modules.etl.validator.OntologyValidator._load_ontology')
@patch('src.modules.etl.validator.OntologyValidator._load_turtle_ontology')
@patch('src.modules.etl.validator.owl.World')
def test_validator_reasoner(mock_world_cls, mock_load_ttl, mock_load_onto, mock_reasoner, dummy_record):
    # Memastikan HermiT reasoner bisa memanggil inferred_types dari INDIRECT_is_a
    validator = OntologyValidator("dummy.ttl")
    
    mock_world = mock_world_cls.return_value
    mock_onto = MagicMock()
    mock_load_ttl.return_value = mock_onto
    
    # Mocking search_one("*#Talent")
    mock_talent_cls = MagicMock()
    mock_world.search_one.side_effect = lambda iri=None, label=None: mock_talent_cls if iri == "*#Talent" else None
    
    temp_talent = MagicMock()
    mock_talent_cls.return_value = temp_talent
    
    inferred_type = MagicMock()
    inferred_type.name = "Talent"
    temp_talent.INDIRECT_is_a = [inferred_type]
    
    res = validator.validate(dummy_record)
    
    assert res.is_valid is True
    assert "Talent" in res.inferred_types


@patch('src.modules.etl.validator.OntologyValidator._load_ontology')
@patch('src.modules.etl.validator.OntologyValidator._load_turtle_ontology')
@patch('src.modules.etl.validator.owl.World')
def test_validator_reasoner_inconsistent(mock_world_cls, mock_load_ttl, mock_load_onto, dummy_record):
    # Memastikan tangkapan error ketika ontologi bentrok (OwlReadyInconsistentOntologyError)
    validator = OntologyValidator("dummy.ttl")
    
    import owlready2
    
    def raise_error(*args, **kwargs):
        raise owlready2.base.OwlReadyInconsistentOntologyError()
        
    with patch('src.modules.etl.validator.sync_reasoner_hermit', side_effect=raise_error):
        res = validator.validate(dummy_record)
    
    assert res.is_valid is False
    assert any("inkonsistensi" in e for e in res.errors)
