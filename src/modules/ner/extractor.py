"""
extractor.py

NERExtractor mengekstrak entitas kebutuhan talenta dari kalimat natural.

Alur:
  1. buildPrompt  — bangun system prompt dengan konteks tanggal WIB
  2. generate     — panggil OllamaClient untuk inferensi LLM
  3. parseResponse — parse JSON dan validasi ke ExtractionResult
"""

from __future__ import annotations

import json

from loguru import logger

from src.core.ollama_client import OllamaClient
from src.modules.ner.schemas import ExtractionResult
# Prompt

_SYSTEM_PROMPT_TEMPLATE = """\
Ekstrak entitas dari kalimat kebutuhan talenta IT ke JSON.

Output JSON wajib berisi field berikut (null/false jika tidak disebutkan):
skills, experience_years_min, location, is_banking_project, education

Aturan:
- skills: nested array (CNF). Outer=AND, Inner=OR.
  "A dan B"        → [["A"], ["B"]]
  "A atau B"       → [["A", "B"]]
  "A dan (B atau C)"→ [["A"], ["B", "C"]]
  "React dan UI/UX" → [["React.js"], ["UI/UX"]]
  "menguasai React.js dan paham TypeScript" → [["React.js"], ["TypeScript"]]
  "php (laravel / codeigniter)" → [["PHP"], ["Laravel", "CodeIgniter"]]
  "javascrip (reak sama nod js)" → [["JavaScript"], ["React.js"], ["Node.js"]]
  "Golang atau Java" → [["Golang", "Java"]]
  Normalisasi nama (typo/singkatan → nama resmi): japa→Java, reakt→React.js, go→Golang, angular→Angular
  Kata "atau" / "/" dalam satu skill group → masuk inner array yang sama (OR).
  Kata "dan" / "sama" → selalu pisahkan ke outer array yang berbeda (AND).
  **PENTING**: JANGAN mengekstrak peran/jabatan umum (seperti BE, FE, Backend, Frontend, Fullstack, Developer, Programmer, Engineer, Project Manager, Scrum Master, Data Engineer, Site Reliability Engineer, QA, Sysadmin, dsb.) sebagai skill. Skill harus berupa nama teknologi spesifik (seperti Java, Python, React.js, AWS, DevOps, UI/UX, QA Automation, dsb.).
- experience_years_min: angka desimal, bukan string. Aturan:
  - Jika ada angka tahun spesifik (misal "min 3 tahun"), gunakan angka itu (contoh: 3.0).
  - Jika tidak ada angka eksplisit: "junior" = 1.0, "middle"/"mid" = 2.0, "senior" = 5.0.
  - Jika fresh grad (fresgrad, magang) atau tidak ada petunjuk pengalaman, kembalikan null.
- location: nama kota lengkap (normalisasi: bdg→Bandung, jkt→Jakarta, sby→Surabaya)
- is_banking_project: boolean. True jika proyek terkait sektor perbankan, bank, fintech. False jika tidak disebutkan atau sektor lain (e-commerce, telco, dsb).
- education: flat array jenjang pendidikan (opsi valid: "SMA/SMK", "D1", "D2", "D3", "D4", "S1", "S2", "S3").
  Aturan:
  - Ekstrak hanya jenjang pendidikan yang disebutkan secara eksplisit dalam query (normalisasi: "sarjana" -> "S1", "diploma" -> "D3").
  - Jika query meminta batas minimal seperti "minimal D3", hanya kembalikan ["D3"]. Jangan pernah menambahkan SMA/SMK atau jenjang lainnya.
  - Jika query meminta beberapa opsi spesifik seperti "D3 atau S1", kembalikan ["D3", "S1"].
  - Jika tidak disebutkan, kembalikan null.

Contoh:
Q: "senior react min 3 thn, bdg, fintech, minimal S1"
A: {{"skills":[["React.js"]],"experience_years_min":3,"location":"Bandung","is_banking_project":true,"education":["S1"]}}

Q: "butuh japa developer, jkt, pengalaman 5 tahun, Pendidikan SMK"
A: {{"skills":[["Java"]],"experience_years_min":5,"location":"Jakarta","is_banking_project":false,"education":["SMA/SMK"]}}

Q: "Saya butuh developer web yang menguasai React.js dan paham UI/UX, penempatan di Bandung, tidak untuk industri perbankan ya, minimal sarjana"
A: {{"skills":[["React.js"],["UI/UX"]],"experience_years_min":null,"location":"Bandung","is_banking_project":false,"education":["S1"]}}

Q: "butuh React atau Vue, D3/S1, min 3 tahun"
A: {{"skills": [["React.js", "Vue.js"]], "experience_years_min": 3, "location": null, "is_banking_project": false, "education": ["D3", "S1"]}}

Q: "Python dan (Postgres atau MySQL), S1, senior"
A: {{"skills": [["Python"], ["PostgreSQL", "MySQL"]], "experience_years_min": 5.0, "location": null, "is_banking_project": false, "education": ["S1"]}}

Q: "fresh grad python, perbankan"
A: {{"skills":[["Python"]],"experience_years_min":null,"location":null,"is_banking_project":true,"education":null}}

Q: "ada talent available?"
A: {{"skills":[],"experience_years_min":null,"location":null,"is_banking_project":false,"education":null}}

Q: "Butuh devops sekalian yang jago AWS, minimal lulusan D3, project bank nih cuy, jakarta"
A: {{"skills":[["DevOps"],["AWS"]],"experience_years_min":null,"location":"Jakarta","is_banking_project":true,"education":["D3"]}}

Q: "Butuh talent BE untuk proyek baru"
A: {{"skills":[],"experience_years_min":null,"location":null,"is_banking_project":false,"education":null}}

Q: "Mencari developer frontend di Jakarta minimal D3"
A: {{"skills":[],"experience_years_min":null,"location":"Jakarta","is_banking_project":false,"education":["D3"]}}

Kembalikan HANYA objek JSON, tanpa teks lain.\
"""

class NERExtractor:
    """
    Mengekstrak entitas kebutuhan talenta dari kalimat natural.

    Dependency injection pada constructor memudahkan unit testing —
    OllamaClient bisa diganti dengan mock tanpa menyentuh HTTP.
    """

    def __init__(self, client: OllamaClient | None = None) -> None:
        self.client = client or OllamaClient()

    async def extract(self, query: str) -> ExtractionResult:
        """
        Ekstrak entitas dari satu kalimat query.

        Parameters
        ----------
        query : str
            Kalimat kebutuhan talenta dari pengguna.

        Returns
        -------
        ExtractionResult
            Objek terstruktur berisi ketujuh slot entitas.
        """
        logger.info(f"Memulai ekstraksi | query='{query}'")

        system_prompt = self._build_prompt()

        raw_json = await self.client.generate(system_prompt, query)
        result = self._parse_response(raw_json, query)

        logger.info(
            f"Ekstraksi selesai | skills={result.skills} "
            f"location={result.location} education={result.education}"
        )
        return result

    def _build_prompt(self) -> str:
        """Build system prompt untuk ekstraksi entitas."""
        return _SYSTEM_PROMPT_TEMPLATE

    def _parse_response(self, raw_json: str, query: str) -> ExtractionResult:
        """
        Parse teks JSON dari Ollama menjadi ExtractionResult.

        Menangani markdown code fence yang kadang muncul
        meski format:json sudah diset.
        """
        cleaned = self._clean_json_string(raw_json)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.error(f"Gagal parse JSON | error={exc} | raw={raw_json[:200]}")
            raise ValueError(f"Respons Ollama bukan JSON valid: {exc}") from exc

        raw_location = data.get("location")
        if isinstance(raw_location, list):
            raw_location = raw_location[0] if raw_location else None
        elif raw_location is not None:
            raw_location = str(raw_location)
            
        # Kecil tapi bermakna: filter lokasi jika ada negasi eksplisit
        q_lower = query.lower()
        if raw_location and ("jangan di" in q_lower or "bukan" in q_lower):
            raw_location = None

        education = self._parse_education(data.get("education"))

        explicit_edu = self._extract_education_from_text(q_lower)
        if explicit_edu:
            education = explicit_edu

        experience = self._parse_experience(data.get("experience_years_min"))


        seniority_words = {"senior", "junior", "middle", "mid", "tahun", "thn", "taunan", "yr", "years"}
        has_seniority = any(w in q_lower.split() or w in q_lower for w in seniority_words)
        if not has_seniority and experience is not None:
            experience = None

        blacklist = {"developer", "developper", "programmer", "engineer", "backend", "frontend", "fullstack", "project manager", "scrum master", "data engineer", "data engineering", "site reliability engineer", "sre", "qa", "sysadmin", "magang", "teknisi", "teknisi jaringan"}
        raw_skills = data.get("skills") or []
        filtered_skills = []
        for g in raw_skills:
            if isinstance(g, str) and g.lower() not in blacklist:
                filtered_skills.append([g])
            elif isinstance(g, list):
                fg = [s for s in g if str(s).lower() not in blacklist]
                if fg: filtered_skills.append(fg)

        return ExtractionResult(
            query=query,
            skills=filtered_skills,
            experience_years_min=experience,
            location=raw_location,
            is_banking_project=bool(data.get("is_banking_project", False)),
            education=education,
        )

    def _parse_experience(self, raw: object) -> float | None:
        """
        Konversi experience_years_min ke float.

        LLM kadang mengembalikan float (3.0) meski diinstruksikan integer.
        Konversi ke float untuk konsistensi skema.
        """
        if raw is None:
            return None
        try:
            return float(str(raw))
        except (ValueError, TypeError):
            logger.warning(f"experience_years_min tidak valid: {raw!r}")
            return None

    def _parse_education(self, raw: object) -> list[str] | None:
        """
        Validasi dan normalisasi field education.

        Menerima list string atau null dari LLM.
        List kosong dikonversi ke null — tidak ada bedanya secara semantik.
        """
        if not raw:
            return None
        if not isinstance(raw, list):
            logger.warning(f"Education bukan list: {raw!r}")
            return None

        # Mapping normalisasi untuk mengatasi typo/variasi dari LLM
        norm_map = {
            "s1": "S1",
            "s2": "S2",
            "s3": "S3",
            "s,": "S1",
            "s": "S1",
            "s.1": "S1",
            "sarjana": "S1",
            "diploma": "D3",
            "d1": "D1",
            "d2": "D2",
            "d3": "D3",
            "d4": "D4",
            "smk": "SMA/SMK",
            "sma": "SMA/SMK",
            "sma/smk": "SMA/SMK",
        }

        cleaned = []
        for e in raw:
            if not e:
                continue
            item = str(e).strip().lower()
            norm_val = norm_map.get(item) or str(e).strip()
            cleaned.append(norm_val)

        if not cleaned:
            return None
        return cleaned

    @staticmethod
    def _extract_education_from_text(q_lower: str) -> list[str] | None:
        """
        Ekstrak jenjang pendidikan secara deterministik langsung dari teks query.
        Menggantikan keputusan LLM jika ada kata kunci pendidikan yang eksplisit.
        """
        import re

        edu_patterns = [
            (r"\bs[./ ]?3\b|doktor",       "S3"),
            (r"\bs[./ ]?2\b|magister",      "S2"),
            (r"\bs[./ ]?1\b|sarjana",       "S1"),
            (r"\bd[./ ]?4\b",               "D4"),
            (r"\bd[./ ]?3\b|diploma",       "D3"),
            (r"\bd[./ ]?2\b",               "D2"),
            (r"\bd[./ ]?1\b",               "D1"),
            (r"\bsma\b|\bsmk\b|sma/smk",   "SMA/SMK"),
        ]

        found = []
        for pattern, label in edu_patterns:
            if re.search(pattern, q_lower) and label not in found:
                found.append(label)

        return found if found else None

    @staticmethod
    def _clean_json_string(text: str) -> str:
        """Hapus markdown code fence kalau ada."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            cleaned = "\n".join(lines[1:-1]).strip()
        return cleaned
