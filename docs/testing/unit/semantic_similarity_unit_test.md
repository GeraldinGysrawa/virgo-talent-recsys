# Dokumentasi Unit Test Modul Semantic Similarity

## 1. Ringkasan Modul
Modul `semantic_similarity` digunakan untuk menghitung kecocokan semantik antara *skill requirement* (dari ekstraksi NER) dan *skill talent* (kandidat) berdasarkan ontologi/graf skill yang tersimpan di Neo4j. Modul ini menyediakan layanan pencocokan cerdas yang mendukung kebutuhan tunggal maupun disjungtif (OR).

## 2. Environment Pengujian
- **Framework**: `pytest`
- **Environment**: Local virtual environment `venv`
- **Command Umum**:
  ```powershell
  $env:PYTHONPATH="."; .\venv\Scripts\python.exe -m pytest tests/unit/modules/semantic_similarity/
  ```
- **Catatan**: Unit test dijalankan murni secara terisolasi tanpa *Docker* dan tanpa koneksi ke *database* Neo4j asli. *Dependency* eksternal (seperti `neo4j.Driver`) akan di-*mock* pada file pengujian yang membutuhkannya.

## 3. Struktur File Test
Rencana struktur file pengujian di dalam repositori:
```text
tests/unit/modules/semantic_similarity/
├── test_skill_requirement.py
├── test_sanchez.py
├── test_skill_graph.py
├── test_similarity_service.py
├── test_ic_precompute_v2.py
└── test_matcher.py
```

## 4. Progress Pengujian
| No | Komponen | File Test | Status | Keterangan |
|---|---|---|---|---|
| 1 | `skill_requirement.py` | `test_skill_requirement.py` | Selesai / Lulus | 7/7 passed |
| 2 | `sanchez.py` | `test_sanchez.py` | Selesai / Lulus | 5/5 passed |
| 3 | `skill_graph.py` | `test_skill_graph.py` | Selesai / Lulus | 7/7 passed |
| 4 | `similarity_service.py`| `test_similarity_service.py`| Selesai / Lulus | 4/4 passed |
| 5 | `ic_precompute_v2.py` | `test_ic_precompute_v2.py` | Selesai / Lulus | 5/5 passed |
| 6 | `matcher.py` | `test_matcher.py` | Selesai / Lulus | 6/6 passed |

## 5. Detail Pengujian Komponen

### 5.1 Pengujian skill_requirement.py
- **Source file**: `src/modules/semantic_similarity/skill_requirement.py`
- **Test file**: `tests/unit/modules/semantic_similarity/test_skill_requirement.py`
- **Jenis test**: Unit Test
- **Dependency eksternal**: tidak ada
- **Mocking**: tidak diperlukan
- **Command**:
  ```powershell
  $env:PYTHONPATH="."; .\venv\Scripts\python.exe -m pytest tests/unit/modules/semantic_similarity/test_skill_requirement.py
  ```
- **Hasil**: 7 test passed
- **Source code utama diubah**: tidak

**Daftar Test Case:**
| Nama Fungsi Test | Skenario Pengujian |
|---|---|
| `test_parse_empty_input` | Memastikan input kosong (`[]`) menghasilkan hasil yang kosong. |
| `test_parse_single_group_single_skill` | Memastikan parsing satu grup dengan satu skill (contoh: `[["React"]]`). |
| `test_parse_single_group_multiple_skills`| Memastikan satu grup dengan beberapa skill dianggap disjunctive (OR logic). |
| `test_parse_multiple_groups` | Memastikan beberapa grup terpisah diurai menjadi objek mandiri secara urut. |
| `test_parse_empty_strings_and_spaces` | Memastikan array yang berisi spasi kosong diabaikan/dibersihkan. |
| `test_parse_handles_non_strings` | Memastikan tidak terjadi error jika element berisi data non-string. |
| `test_skill_requirement_dataclass_properties` | Memvalidasi property dan return value saat objek dataclass diinisiasi langsung. |

### 5.2 Pengujian sanchez.py
- **Source file**: `src/modules/semantic_similarity/sanchez.py`
- **Test file**: `tests/unit/modules/semantic_similarity/test_sanchez.py`
- **Jenis test**: Unit Test
- **Dependency eksternal**: `SkillGraph`
- **Mocking**: Menggunakan `unittest.mock.MagicMock` untuk memalsukan method `get_by_label` dan `subsumers` dari `SkillGraph` sehingga mengembalikan *dummy* `SkillNode` dan himpunan URI buatan.
- **Command**:
  ```powershell
  $env:PYTHONPATH="."; .\venv\Scripts\python.exe -m pytest tests/unit/modules/semantic_similarity/test_sanchez.py
  ```
- **Hasil**: 5 test passed
- **Source code utama diubah**: tidak

**Daftar Test Case:**
| Nama Fungsi Test | Skenario Pengujian |
|---|---|
| `test_similarity_identical_labels` | Memastikan kemiripan antara dua label skill yang persis sama mengembalikan 1.0 (meskipun case-insensitive). |
| `test_similarity_missing_label` | Memastikan fungsi langsung mengembalikan 0.0 jika salah satu skill tidak ada di ontologi/graph. |
| `test_similarity_partial_overlap` | Memastikan algoritma disnorm (Sánchez) berjalan jika ada himpunan subsumers yang beririsan (mengembalikan nilai antara 0 dan 1 secara eksak). |
| `test_similarity_by_uri_direct` | Menguji jalur langsung menggunakan URI dan memvalidasi jika himpunan saling asing mengembalikan skor 0.0. |
| `test_similarity_empty_subsumers`| Menguji *edge case* jika ontologi mengembalikan list *subsumer* kosong (union=0) agar tidak terjadi Division by Zero, mengembalikan skor 0.0. |

### 5.3 Pengujian skill_graph.py
- **Source file**: `src/modules/semantic_similarity/skill_graph.py`
- **Test file**: `tests/unit/modules/semantic_similarity/test_skill_graph.py`
- **Jenis test**: Unit Test
- **Dependency eksternal**: `neo4j.Driver`, `neo4j.Session`
- **Mocking**: Menggunakan `unittest.mock.MagicMock` untuk memalsukan respon dari Neo4j Cypher `session.run()` agar mengembalikan list of dict layaknya *record database*.
- **Command**:
  ```powershell
  $env:PYTHONPATH="."; .\venv\Scripts\python.exe -m pytest tests/unit/modules/semantic_similarity/test_skill_graph.py
  ```
- **Hasil**: 7 test passed
- **Source code utama diubah**: tidak

**Daftar Test Case:**
| Nama Fungsi Test | Skenario Pengujian |
|---|---|
| `test_skill_graph_load_success` | Memastikan graph berhasil memuat node/class dan relasi parent-child secara parsial dari hasil mock Neo4j. |
| `test_get_by_label` | Memastikan metode `get_by_label()` mencari dan mengembalikan URI/node yang benar secara case-insensitive. |
| `test_get_by_label_unknown` | Memastikan balikan yang aman (None) jika URI/label tidak ditemukan. |
| `test_subsumers_logic_and_caching` | Memastikan algoritma pencarian lelulur (*ancestors*) berjalan merunut ke root, dan hasil akhirnya di-cache untuk mempercepat eksekusi berikutnya. |
| `test_subsumers_unknown_uri` | *Edge case* jika mencari subsumer dari URI yang invalid maka akan mengembalikan himpunan yang hanya berisi URI itu sendiri. |
| `test_fallback_query` | Memastikan fallback query (tanpa filter `padepokan79`) dieksekusi oleh Neo4j *driver* jika query utama kosong. |
| `test_empty_label_and_uri_fallback` | Menguji toleransi parser jika properti label node kembalian Neo4j kosong (mengambil *suffix* URI) atau URI-nya tidak valid (dihiraukan). |

### 5.4 Pengujian similarity_service.py
- **Source file**: `src/modules/semantic_similarity/similarity_service.py`
- **Test file**: `tests/unit/modules/semantic_similarity/test_similarity_service.py`
- **Jenis test**: Unit Test
- **Dependency eksternal**: `SkillGraph`, `SanchezSimilarity`, `SkillMatcher`, `ICPrecomputer`
- **Mocking**: Menggunakan `@patch` dari `unittest.mock` untuk memanipulasi inisiasi class-class dependency agar tidak benar-benar mengeksekusi koneksi Neo4j dan logic internal.
- **Command**:
  ```powershell
  $env:PYTHONPATH="."; .\venv\Scripts\python.exe -m pytest tests/unit/modules/semantic_similarity/test_similarity_service.py
  ```
- **Hasil**: 4 test passed
- **Source code utama diubah**: tidak

**Daftar Test Case:**
| Nama Fungsi Test | Skenario Pengujian |
|---|---|
| `test_service_uninitialized_state` | Memastikan service menolak eksekusi `rank_talents()` dan `recompute_ic_similarity()` (melempar `RuntimeError`) jika `initialize()` belum dipanggil. |
| `test_initialize_and_reload` | Memastikan `initialize()` dan `reload()` sukses membuat instansi dependensi (`SkillGraph`, dll) dengan argumen konstruktor yang presisi. |
| `test_rank_talents_passthrough` | Memastikan method meneruskan (*pass-through*) parameter ke `matcher.match()` dan mengembalikan nilainya tanpa distorsi. |
| `test_recompute_ic_similarity_passthrough` | Memastikan method menginisiasi `ICPrecomputer` dengan referensi memori yang tepat dan meneruskan pemanggilan `run()`. |

### 5.5 Pengujian ic_precompute_v2.py
- **Source file**: `src/modules/semantic_similarity/ic_precompute_v2.py`
- **Test file**: `tests/unit/modules/semantic_similarity/test_ic_precompute_v2.py`
- **Jenis test**: Unit Test
- **Dependency eksternal**: `neo4j.Driver`, `SkillGraph`, `SanchezSimilarity`
- **Mocking**: Menggunakan `unittest.mock.MagicMock` untuk memalsukan respon dari graf/ontologi dan kembalian `session.run()`, serta menggunakan `@patch` untuk merekayasa variabel konstanta internal `_BATCH_SIZE`.
- **Command**:
  ```powershell
  $env:PYTHONPATH="."; .\venv\Scripts\python.exe -m pytest tests/unit/modules/semantic_similarity/test_ic_precompute_v2.py
  ```
- **Hasil**: 5 test passed
- **Source code utama diubah**: tidak

**Daftar Test Case:**
| Nama Fungsi Test | Skenario Pengujian |
|---|---|
| `test_run_success_and_delete_old_data` | Memastikan proses iterasi kombinasi antar skill berjalan sempurna, kalkulasi `similarity` dipanggil, dan relasi lama dihapus lebih dulu via `DELETE r`. |
| `test_batching_mechanism` | Menguji fitur *batch-write* (memecah penulisan query menjadi kelompok kecil untuk menghindari time-out Neo4j) dengan mem-*patch* variabel `_BATCH_SIZE`. |
| `test_empty_uris` | Edge case: Jika daftar array skill kosong, precomputer harus berhenti tanpa eksekusi `MERGE` tapi tetap diizinkan memanggil fungsi `_clear_old_data()`. |
| `test_single_uri` | Edge case: Memastikan logika `itertools.combinations` tidak bermasalah (mengembalikan 0 pasang) apabila array uri hanya berjumlah satu buah. |
| `test_write_error_handling` | Mensimulasikan terjadinya *error database/timeout* saat eksekusi Neo4j Cypher `MERGE`, kemudian memvalidasi bahwa error dicatat di dalam log/property `errors` secara aman tanpa memberhentikan aplikasi secara total. |

### 5.6 Pengujian matcher.py
- **Source file**: `src/modules/semantic_similarity/matcher.py`
- **Test file**: `tests/unit/modules/semantic_similarity/test_matcher.py`
- **Jenis test**: Unit Test
- **Dependency eksternal**: `SkillGraph`, `SanchezSimilarity`, `neo4j.Driver`, `neo4j.Session`
- **Mocking**: Menggunakan `@patch.object` dari `unittest.mock` untuk mencegat *method* internal kelas seperti `_check_similarity_available` dan `_fetch_talent_skills`, serta mensimulasikan hasil respon *Cypher Query* Neo4j untuk kalkulasi *precomputed*.
- **Command**:
  ```powershell
  $env:PYTHONPATH="."; .\venv\Scripts\python.exe -m pytest tests/unit/modules/semantic_similarity/test_matcher.py
  ```
- **Hasil**: 6 test passed
- **Source code utama diubah**: tidak

**Daftar Test Case:**
| Nama Fungsi Test | Skenario Pengujian |
|---|---|
| `test_matcher_initialization` | Memastikan *instance* terbuat dengan atribut yang menyimpan semua *mock dependency* eksternal secara akurat. |
| `test_matcher_empty_or_invalid_requirements` | Uji *edge case* di mana list *requirement* kosong atau semua *requirement* mengandung skill yang tidak dikenali ontologi. Kembalian dipastikan list kosong (`[]`). |
| `test_fallback_disjunctive_logic` | Menguji mode *fallback* (perhitungan *on-the-fly*). Validasi algoritma bahwa jika skill disjungtif (di dalam *array group* yang sama), matcher mengambil skor tertinggi (*OR logic*). |
| `test_fallback_and_average_logic` | Validasi algoritma kalkulasi *Best Match Average* antargrup (*AND logic*) berjalan matematis dengan presisi. |
| `test_neo4j_mode` | Memaksa matcher menggunakan jalur eksekusi Neo4j (`SKILL_SIMILARITY` exists), mem-*mock* kembalian *session*, dan memastikan skor hasil akhir diekstrak dari database. |
| `test_talent_without_skills` | Uji *edge case* mengembalikan *score* aman 0.0 jika talent yang direkam ternyata tidak memiliki himpunan skill sama sekali. |

## 6. Kesimpulan Akhir
Keseluruhan pembuatan *unit test* untuk modul **`semantic_similarity`** (Tahap Increment 2) telah **sukses dan selesai**. Keenam file kunci di dalam modul (`skill_requirement.py`, `sanchez.py`, `skill_graph.py`, `similarity_service.py`, `ic_precompute_v2.py`, dan `matcher.py`) berhasil dievaluasi secara terisolasi tanpa membutuhkan koneksi *database* Neo4j yang aktif dengan memanfaatkan strategi *mocking* dan *patching*.

- **Total Keseluruhan Test Case**: 34 Test
- **Total Kegagalan/Error**: 0
- **Total Modifikasi Source Code**: 0 (Desain struktur modul aslinya sudah terbukti sangat solid dan mendukung paradigma *Dependency Injection* yang memudahkan pengujian unit).
- **Kecepatan Uji (Full Suite)**: Sangat kencang, di bawah ~1.0 detik.

Modul ini telah tervalidasi keandalannya pada tingkat unit dan siap untuk menghadapi tahapan *Integration Test* maupun implementasi sistem produksi *recommender*.
