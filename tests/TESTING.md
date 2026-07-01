# Panduan Eksekusi Test — Virgo Talent ReqSys

## Ringkasan

| Grup | File | Kode WB | Coverage Target |
|---|---|---|---|
| SAW | `tests/unit/test_roc_weight_calculator.py` | WB-SAW-01 | ≥80% |
| SAW | `tests/unit/test_saw_ranker.py` | WB-SAW-02 | ≥80% |
| SAW | `tests/unit/test_saw_service.py` | WB-SAW-03 | ≥80% |
| SAW | `tests/unit/test_rank_result_formatter.py` | WB-SAW-04 | ≥80% |
| SAW | `tests/integration/test_saw_endpoint.py` | WB-SAW-05 | ≥80% |
| NER | `tests/unit/test_ner_extractor.py` | WB-NER-01..03 | ≥80% |
| Similarity | `tests/unit/test_skill_matcher.py` | WB-SIM-01 | ≥80% |
| Similarity | `tests/unit/test_sanchez_similarity.py` | WB-SIM-02 | ≥80% |
| ETL | `tests/unit/test_etl_transformer.py` | WB-ETL-01 | ≥60% |
| ETL | `tests/unit/test_etl_validator.py` | WB-ETL-02 | ≥60% |
| ETL | `tests/unit/test_skill_normalizer.py` | WB-ETL-03 | ≥60% |
| ETL | `tests/unit/test_neo4j_writer.py` | WB-ETL-04 | ≥60% |

---

## Prerequisites

Pastikan dependensi sudah terinstal:

```bash
pip install -r requirements.txt --break-system-packages
```

Tidak diperlukan: Neo4j, Ollama, Docker, atau koneksi jaringan. Semua
external dependency di-mock oleh test suite.

**Khusus WB-ETL-02** (`test_etl_validator.py`): membutuhkan `owlready2`
dan `rdflib` (sudah ada di `requirements.txt`). Test ini juga membutuhkan
file fixture `tests/fixtures/test_ontology.ttl` — sudah disertakan.
Reasoner HermiT (membutuhkan Java) berjalan jika tersedia; jika tidak,
hanya validasi struktural yang dijalankan.

---

## JC-10 — Eksekusi Seluruh Test White-Box

```bash
pytest tests/unit/ -v --cov=src --cov-report=term-missing
```

Perintah ini:
- Menjalankan semua 12 file test unit (WB-SAW-01..04, WB-NER-01..03, WB-SIM-01..02, WB-ETL-01..04)
- Menghasilkan laporan coverage per baris (`--cov-report=term-missing`)
- Verbose output (`-v`) menampilkan nama tiap test case

---

## Eksekusi Per Modul

```bash
# SAW (semua unit + integration)
pytest tests/unit/test_roc_weight_calculator.py tests/unit/test_saw_ranker.py \
       tests/unit/test_saw_service.py tests/unit/test_rank_result_formatter.py \
       tests/integration/test_saw_endpoint.py -v

# NER
pytest tests/unit/test_ner_extractor.py -v

# Semantic Similarity
pytest tests/unit/test_skill_matcher.py tests/unit/test_sanchez_similarity.py -v

# ETL
pytest tests/unit/test_etl_transformer.py tests/unit/test_etl_validator.py \
       tests/unit/test_skill_normalizer.py tests/unit/test_neo4j_writer.py -v
```

---

## Eksekusi Termasuk Integration Test

```bash
pytest tests/ -v --cov=src --cov-report=term-missing
```

---

## Menghasilkan Laporan Coverage HTML

```bash
pytest tests/unit/ --cov=src --cov-report=html
# Buka htmlcov/index.html di browser
```

---

## Interpretasi Coverage per Modul

Setelah run, cek baris `TOTAL` dan per-file di output. Coverage aktual
dicatat di kolom **Coverage Aktual (%)** pada sheet `TC_WhiteBox` workbook
`VRG-TC_Kompilasi_Test_Case.xlsx`.

Threshold yang harus dipenuhi sebelum merge ke main:

| Modul | Threshold | Blocking |
|---|---|---|
| SAW | ≥80% | Increment 3 |
| NER | ≥80% | Increment 1 |
| Similarity | ≥80% | Increment 2 |
| ETL | ≥60% | Increment 2 |

---

## Troubleshooting

**`ModuleNotFoundError: src`** — jalankan pytest dari root project (direktori
yang berisi `src/` dan `tests/`):
```bash
cd /path/to/virgo-talent-recsys
pytest tests/unit/ -v --cov=src
```

**`owlready2` tidak terinstal** — `test_etl_validator.py` otomatis di-skip
dengan `pytest.importorskip`. Instal via:
```bash
pip install owlready2 rdflib --break-system-packages
```

**`asyncio_mode` warning** — sudah dikonfigurasi di `pytest.ini`. Pastikan
`pytest-asyncio==0.24.0` terinstal.

**Test `test_saw_endpoint.py` gagal import** — pastikan `fastapi` dan `httpx`
terinstal (keduanya ada di `requirements.txt`).

---

## Struktur File

```
tests/
├── conftest.py                    # Shared config & path fixture
├── fixtures/
│   └── test_ontology.ttl          # Ontologi minimal untuk WB-ETL-02
├── unit/
│   ├── test_roc_weight_calculator.py   # WB-SAW-01
│   ├── test_saw_ranker.py              # WB-SAW-02
│   ├── test_saw_service.py             # WB-SAW-03
│   ├── test_rank_result_formatter.py   # WB-SAW-04
│   ├── test_ner_extractor.py           # WB-NER-01..03
│   ├── test_skill_matcher.py           # WB-SIM-01
│   ├── test_sanchez_similarity.py      # WB-SIM-02
│   ├── test_etl_transformer.py         # WB-ETL-01
│   ├── test_etl_validator.py           # WB-ETL-02
│   ├── test_skill_normalizer.py        # WB-ETL-03
│   └── test_neo4j_writer.py            # WB-ETL-04
└── integration/
    └── test_saw_endpoint.py            # WB-SAW-05
```
