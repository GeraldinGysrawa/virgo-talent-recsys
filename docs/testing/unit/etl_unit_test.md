# Dokumentasi Unit Test Modul ETL

Dokumen ini berisi pencatatan (log) progres dan metodologi yang digunakan dalam pengujian level unit untuk komponen-komponen utama pada modul `etl` (`src/modules/etl`).

## 1. Ringkasan Modul
Modul `etl` bertanggung jawab untuk mengorkestrasi alur data talenta dari Google Sheets menuju basis data graf Neo4j. Proses ini mencakup ekstraksi data, transformasi pembersihan, normalisasi *skill*, validasi ontologi menggunakan *reasoner* eksternal (HermiT), dan penulisan transaksi basis data secara *batch*.

## 2. Environment Pengujian
- **Framework**: `pytest`
- **Environment**: Local virtual environment `venv`
- **Isolasi Eksternal**: Keseluruhan pengujian dilakukan tanpa melakukan pemanggilan aktual ke Google API, Neo4j, maupun pembacaan file sistem `.ttl` berkat pemanfaatan taktik *mocking* secara ekstensif (`unittest.mock`).
- **Command Utama**:
  ```powershell
  $env:PYTHONPATH="."; .\venv\Scripts\python.exe -m pytest tests/unit/modules/etl/
  ```

## 3. Daftar File yang Diuji

Pengujian modul ETL mencakup keseluruhan 6 skrip *source code* yang ada, yang menghasilkan **20 Test Case**. Seluruhnya berstatus lulus (100% Passed).

| No | File Utama | File Pengujian | Status | Hasil Akhir |
|---|---|---|---|---|
| 1 | `sheets_reader.py` | `test_sheets_reader.py` | Selesai / Lulus | 2/2 passed |
| 2 | `skill_normalizer.py`| `test_skill_normalizer.py` | Selesai / Lulus | 7/7 passed |
| 3 | `transformer.py` | `test_transformer.py` | Selesai / Lulus | 3/3 passed |
| 4 | `validator.py` | `test_validator.py` | Selesai / Lulus | 4/4 passed |
| 5 | `neo4j_writer.py` | `test_neo4j_writer.py` | Selesai / Lulus | 2/2 passed |
| 6 | `pipeline.py` | `test_pipeline.py` | Selesai / Lulus | 2/2 passed |

---

## 4. Rincian Metodologi Pengujian Per Komponen

### 4.1. `sheets_reader.py`
- **Mocking**: Menghentikan otentikasi Google Cloud dengan mem-_patch_ `gspread.authorize` dan `Credentials.from_service_account_file`. Memanipulasi nilai `worksheet.get_all_records()`.
- **Skenario Validasi**: Memastikan bahwa kolom angka seperti "00123" pada *NIP* dipertahankan sebagai tipe data `string`, dan data dengan status NIP kosong secara langsung disisihkan dari pemrosesan.

### 4.2. `skill_normalizer.py`
- **Mocking**: Simulasi _flag_ `_RAPIDFUZZ_AVAILABLE` yang diatur ke `False` untuk membuktikan _fallback logic_ bekerja dengan baik.
- **Skenario Validasi**: Pengujian pencarian eksak, pengalihan berbasis _alias map_, penanganan kesalahan (_not found_), hingga pemecahan karakter ampersand (`&`) dan _fuzzy string matching_ dengan _threshold_.

### 4.3. `transformer.py`
- **Mocking**: Mem-_patch_ instansi `SkillNormalizer` agar dapat mengembalikan hasil statis buatan.
- **Skenario Validasi**: Konversi teks kotor (spasi, angka string) menjadi tipe primitif terstandarisasi, serta konversi tanggal kompeks mulai dari tipe Serial 1899 hingga format "DD/MM/YYYY" dan penanganan eror jenis lokasi penempatan (*ValueError*).

### 4.4. `validator.py`
- **Mocking**: Simulasi kelas manipulasi struktur *Owlready2* (`owl.World()`) dan *RDFLib Graph* termasuk simulasi hasil pembacaan _reasoner_ HermiT via `sync_reasoner_hermit()`.
- **Skenario Validasi**: Memastikan bahwa *instance* menyuntikkan _Inferred Types_ ke memori program secara transparan saat ada entitas individu baru (_Talent_) yang dideklarasikan. Penangkapan (*catch*) kesalahan eksternal `OwlReadyInconsistentOntologyError`.

### 4.5. `neo4j_writer.py`
- **Mocking**: Pencegatan `GraphDatabase.driver` yang difokuskan pada _spy_ fungsi `session.begin_transaction()` serta penangkapan `tx.run()`.
- **Skenario Validasi**: Uji verifikasi apakah skrip penulisan _Project_ telah menyertakan instruksi `DELETE r` untuk skema membersihkan properti relasi yang usang, serta simulasi terjadinya kesalahan koneksi internet (skenario *failure* `Exception`).

### 4.6. `pipeline.py`
- **Mocking**: Melakukan *full-mock* terhadap komponen-komponen *sibling* (yakni *Reader, Validator, Normalizer, Transformer,* dan *Writer*).
- **Skenario Validasi**: Memastikan urutan sinkron berjalan sempurna. Jika data mentah tidak ditemukan sejak tahap pembacaan _Sheets_, proses harus digagalkan dengan laporan kosong.

---

## 5. Kesimpulan
Seluruh komponen modul ETL (Increment 2) telah dilindungi oleh pengujian skala unit. Kode telah terbukti sangat *testable*, dapat di-*mock* secara independen, serta menangani seluruh celah perbatasan data (_edge cases_) tanpa harus melakukan manipulasi modifikasi _source code_ asal. Kecepatan _Full Suite Runner_ juga berada pada kategori optimal (di bawah 1.5 detik), memastikan beban pengembangan tetap terisolasi dengan aman.
