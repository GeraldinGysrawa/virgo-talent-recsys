# =============================================================
# skill_normalizer.py
# Modul ETL — Increment 2: Semantic Similarity
#
# Tanggung Jawab:
#   Menangani keragaman penulisan skill dari spreadsheet
#   sebelum data diteruskan ke validator dan Neo4j writer.
#
# Arsitektur tiga lapisan (sesuai pola NER Increment 1):
#   Lapisan 1 — Rule-based (alias map deterministik)
#   Lapisan 2 — Fuzzy matching (rapidfuzz, threshold ≥ 85)
#   Lapisan 3 — LLM fallback via Ollama [rekomendasi pengembangan]
#
# Penggunaan:
#   normalizer = SkillNormalizer(ontology_labels)
#   canonical, method = normalizer.normalize("Node JS")
#   # → ("Node.js", "alias")
#   # → ("Node.js", "fuzzy:92")
#   # → (None, "not_found") jika tidak ada yang cocok
#
# Referensi:
#   Sánchez, D. et al. (2012) Expert Systems with Applications
#   — normalisasi label adalah prasyarat akurasi IC computation
# =============================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from loguru import logger
import re

try:
    from rapidfuzz import process as rf_process, fuzz
    _RAPIDFUZZ_AVAILABLE = True
except ImportError:
    _RAPIDFUZZ_AVAILABLE = False
    logger.warning(
        "rapidfuzz tidak terinstal. Lapisan 2 (fuzzy) tidak aktif. "
        "Jalankan: pip install rapidfuzz"
    )


# =============================================================
# LAPISAN 1 — Alias Map Deterministik
# Divalidasi terhadap ontology/ttl/Data model v2.ttl (rdfs:label)
# beserta variasi penulisan umum di spreadsheet Indonesia.
#
# Kunci  : variasi penulisan (lowercase, tanpa spasi berlebih)
# Nilai  : rdfs:label kanonik sesuai ontologi
# =============================================================

_ALIAS_MAP: dict[str, str] = {
    "(jira": "JIRA",
    ".net core": "ASP.NET",
    ".net mvc": "ASP.NET",
    ".net mvc javascript": "ASP.NET",
    ".net webcore": "ASP.NET",
    "agile methodology": "Agile/Scrum",
    "alibaba cloud superapp": "Alibaba Cloud",
    "api contract": "Swagger",
    "asp classic": "VBScript",
    "asp.net core": "ASP.NET",
    "big query": "Google BigQuery",
    "bizagi": "Draw.io",
    "bootstrap 5": "Bootstrap",
    "business process model and notation (draw.io)": "Draw.io",
    "c# 10": "C#",
    "chakraui": "Chakra UI",
    "ci": "Jenkins",
    "ci/cd": "Jenkins",
    "cicd jenkins": "Jenkins",
    "cloud provider (biznet)": "AWS",
    "crypto js": "Crypto.js",
    "cucumber)": "Cucumber",
    "d3js": "D3.js",
    "dan laravel": "Laravel",
    "data flow diagram": "DFD",
    "database : postgresql 10": "PostgreSQL",
    "design definition": "API Contract",
    "diagram uml": "UML",
    "docker basic": "Docker",
    "docker hub": "Docker",
    "dokumen tad": "TAD",
    "drawio": "Draw.io",
    "drpc": "gRPC",
    "dubbo": "Apache Dubbo",
    "elastic": "Elasticsearch",
    "elastic search": "Elasticsearch",
    "electron js": "Electron.js",
    "elk": "ELK Stack",
    "erpnext 15": "ERPNext",
    "excell": "Google Sheets",
    "express": "Express.js",
    "express 4.18": "Express.js",
    "express js": "Express.js",
    "expressjs": "Express.js",
    "exspress js": "Express.js",
    "fiber": "Go Fiber",
    "firebase (fcm)": "Firebase",
    "geo server": "GeoServer",
    "geojson/leaflet": "Leaflet",
    "git & github": "Git",
    "gitea": "Git",
    "gitea bizagi": "Git",
    "gitlab": "Git",
    "gofiber": "Go Fiber",
    "google analytics": "Looker Studio",
    "google cloud platform (gcp)": "GCP",
    "google doc": "Google Docs",
    "google sheet": "Google Sheets",
    "google sheet (manual testing)": "QA Manual",
    "google studio": "Looker Studio",
    "gulp js": "Gulp.js",
    "ibatis": "MyBatis",
    "iis 10": "IIS",
    "inertia js": "Inertia.js",
    "insomnia": "Postman",
    "intellij": "IntelliJ IDEA",
    "interacjs": "InteractJS",
    "jasper": "Jasper Report",
    "jasperreport": "Jasper Report",
    "java 17": "Java",
    "java ee": "Java",
    "java fx": "Java Swing",
    "java mvc": "Java",
    "java native": "Java",
    "java spring boot": "Spring Boot",
    "java springboot": "Spring Boot",
    "java springboot versi 2.1": "Spring Boot",
    "java springboot versi 3.0": "Spring Boot",
    "java-quarkus": "Java Quarkus",
    "java-springboot": "Spring Boot",
    "jira)": "JIRA",
    "jitsi engine": "Jitsi",
    "jsonwebtoken": "JWT",
    "jwt security": "JWT",
    "k8s": "Kubernetes",
    "kafka tools": "Kafka",
    "katalon": "Katalon Studio",
    "kibana - elasticsearch": "Elasticsearch",
    "laravel be": "Laravel",
    "laravel blade 9.0": "Laravel",
    "laravel fe": "Laravel",
    "laravel lumen": "Laravel",
    "linter(eslint)": "ESLint",
    "liquiibase": "Liquibase",
    "manual qa": "QA Manual",
    "material ui (mui)": "Material UI",
    "material ui. tailwind css": "Tailwind CSS",
    "material-design": "Material UI",
    "materialui": "Material UI",
    "maven 3.9": "Maven",
    "micro front-end": "Single SPA",
    "microfrontend": "Single SPA",
    "microservices": "Microservice",
    "microservide": "Microservice",
    "microsoft sql server": "SQL Server",
    "min.io object storage": "MinIO",
    "monggodb": "MongoDB",
    "ms sql": "SQL Server",
    "ms sql server": "SQL Server",
    "mui": "Material UI",
    "my sql": "MySQL",
    "mysl": "MySQL",
    "nest js": "Nest.js",
    "nestjs": "Nest.js",
    "net": ".NET",
    "net core": "ASP.NET",
    "net framework 2. .net 9": "ASP.NET",
    "net mvc": "ASP.NET",
    "net mvc javascript": "ASP.NET",
    "net webcore": "ASP.NET",
    "next": "Next.js",
    "next js": "Next.js",
    "next.js. tailwind css": "Next.js",
    "nextjs": "Next.js",
    "nextjs 13.0": "Next.js",
    "node js": "Node.js",
    "nodejs": "Node.js",
    "okd": "OKD/OpenShift",
    "okd (openshift kubernetes distribution)": "OKD/OpenShift",
    "openshift": "OKD/OpenShift",
    "operation contract": "API Contract",
    "oracle": "Oracle DB",
    "oracle sql": "Oracle DB",
    "oracle sql.": "Oracle DB",
    "oracledb": "Oracle DB",
    "owasp zap (zap)": "OWASP ZAP",
    "plant text uml": "PlantUML",
    "postgresl": "PostgreSQL",
    "postgresql & mysql": "PostgreSQL",
    "postgresql 10": "PostgreSQL",
    "postgreswl": "PostgreSQL",
    "postgreysql": "PostgreSQL",
    "power app": "Power Apps",
    "prisma 4.8": "Prisma",
    "project management (jira)": "JIRA",
    "prostgresql": "PostgreSQL",
    "python3 fastapi": "FastAPI",
    "qa automation (cucumber": "QA Automation",
    "qa automation (spreadsheet": "QA Automation",
    "qa manual (sonarqube)": "SonarQube",
    "rabbit mq": "RabbitMQ",
    "radix ui primitive": "Radix UI",
    "react": "React.js",
    "react js": "React.js",
    "react ts": "TypeScript",
    "react-hook-form": "React Hook Form",
    "react-query": "TanStack Query",
    "reactjs": "React.js",
    "rpa": "UIPath (RPA)",
    "s3 aws": "MinIO",
    "s3 browser": "MinIO",
    "scrum framework": "Agile/Scrum",
    "sensor fusion tracking toolbox v2.5": "Statistics Toolbox",
    "server integration service (ssis)": "SSIS",
    "shadcn": "Shadcn/UI",
    "shadcn ui": "Shadcn/UI",
    "spreadsheet": "Google Sheets",
    "spring": "Spring Boot",
    "spring boot 2": "Spring Boot",
    "spring boot 3.3": "Spring Boot",
    "spring boot 3.4": "Spring Boot",
    "spring scheduler": "ElasticJob",
    "springboot": "Spring Boot",
    "springboot (basic)": "Spring Boot",
    "sqfile": "Stacked",
    "sql server 2012": "SQL Server",
    "sql server 2019": "SQL Server",
    "statistics and machine learning toolbox v12.5": "Statistics Toolbox",
    "swaggo": "Swagger",
    "tailwind": "Tailwind CSS",
    "tailwindcss": "Tailwind CSS",
    "talend open studio": "Talend",
    "tanstack": "TanStack Query",
    "tanstack react query": "TanStack Query",
    "tbm spreadsheet": "Google Sheets",
    "termius": "MobaXterm",
    "uipath": "UIPath (RPA)",
    "unified modeling language (uml)": "UML",
    "use case": "Use Case Diagram",
    "vm. server": "VM/Server",
    "vue": "Vue.js",
    "vue js": "Vue.js",
    "web3js 1.10": "Web3.js",
    "websocketserver": "WebSocket",
    "word": "Google Sheets",
    "xray)": "Xray",
    "yaml": "Scripting",
    "yii2": "Yii",
    "—": "Mockito",
}


# =============================================================
# Kelas utama
# =============================================================

@dataclass
class NormalizeResult:
    original    : str
    canonical   : Optional[str]   # label kanonik dari ontologi
    method      : str             # "exact" | "alias" | "fuzzy:NN" | "not_found"
    confidence  : float           # 1.0 = exact/alias, 0.0-1.0 = fuzzy score


class SkillNormalizer:
    """
    Menormalisasi label skill dari spreadsheet ke label kanonik ontologi.

    Lapisan 1 — Alias map deterministik (cepat, tanpa library).
    Lapisan 2 — Fuzzy matching via rapidfuzz (threshold ≥ 85).

    Parameters
    ----------
    ontology_labels : list[str]
        Semua rdfs:label dari ontologi — digunakan oleh lapisan fuzzy.
        Ambil via: [node.label for node in skill_graph.all_nodes()]
    fuzzy_threshold : int
        Threshold minimum skor fuzzy (0-100). Default 85.
    """

    def __init__(
        self,
        ontology_labels : list[str],
        fuzzy_threshold : int = 85,
    ) -> None:
        self._ontology_labels = ontology_labels
        self._threshold       = fuzzy_threshold
        self._fuzzy_available = _RAPIDFUZZ_AVAILABLE

        # Bangun lookup alias: key lowercase → canonical
        self._alias_lookup = {k.lower(): v for k, v in _ALIAS_MAP.items()}

        # Tambahkan mapping otomatis untuk "level-2" labels yang mengandung
        # pemisah seperti '&', '/', ',', ';', 'and' atau '|' sehingga setiap
        # komponen tunggal juga akan map ke label kanonik.
        # Contoh: 'AI & Machine Learning' → 'ai' -> 'AI & Machine Learning',
        #                         'machine learning' -> 'AI & Machine Learning'
        seps_pattern = re.compile(r"\s*(?:&|/|,|;|and|\|)\s*", flags=re.IGNORECASE)
        for label in self._ontology_labels:
            # hanya pertimbangkan label non-empty
            if not label or not isinstance(label, str):
                continue
            parts = seps_pattern.split(label)
            # jika ada lebih dari satu bagian, tambahkan setiap bagian ke lookup
            if len(parts) > 1:
                for p in parts:
                    part = p.strip().lower()
                    if not part:
                        continue
                    # jika belum ada mapping, tambahkan
                    if part not in self._alias_lookup:
                        self._alias_lookup[part] = label

    def normalize(self, raw_label: str) -> NormalizeResult:
        """
        Menormalisasi satu label skill mentah dari spreadsheet.

        Urutan pencarian:
        1. Exact match terhadap label ontologi (case-insensitive)
        2. Alias map deterministik
        3. Fuzzy matching (jika rapidfuzz tersedia)
        4. not_found jika semua lapisan gagal

        Parameters
        ----------
        raw_label : str
            Label skill mentah dari kolom Teknologi spreadsheet.

        Returns
        -------
        NormalizeResult
        """
        cleaned = raw_label.strip()
        lower   = cleaned.lower()

        # ── Lapisan 0: Exact match ke label ontologi ──────
        for label in self._ontology_labels:
            if label.lower() == lower:
                return NormalizeResult(
                    original   = cleaned,
                    canonical  = label,
                    method     = "exact",
                    confidence = 1.0,
                )

        # ── Lapisan 1: Alias map ──────────────────────────
        if lower in self._alias_lookup:
            canonical = self._alias_lookup[lower]
            return NormalizeResult(
                original   = cleaned,
                canonical  = canonical,
                method     = "alias",
                confidence = 1.0,
            )

        # ── Lapisan 2: Fuzzy matching ─────────────────────
        if self._fuzzy_available and self._ontology_labels:
            result = rf_process.extractOne(
                cleaned,
                self._ontology_labels,
                scorer    = fuzz.token_sort_ratio,
                score_cutoff = self._threshold,
            )
            if result is not None:
                match_label, score, _ = result
                logger.info(
                    f"SkillNormalizer [fuzzy]: '{cleaned}' → '{match_label}' "
                    f"(score={score})"
                )
                return NormalizeResult(
                    original   = cleaned,
                    canonical  = match_label,
                    method     = f"fuzzy:{score}",
                    confidence = score / 100.0,
                )

        # ── Tidak ditemukan ───────────────────────────────
        logger.warning(
            f"SkillNormalizer: '{cleaned}' tidak dapat dinormalisasi. "
            f"Skill akan dilewati."
        )
        return NormalizeResult(
            original   = cleaned,
            canonical  = None,
            method     = "not_found",
            confidence = 0.0,
        )

    def normalize_batch(self, raw_labels: list[str]) -> list[NormalizeResult]:
        """
        Menormalisasi seluruh daftar skill sekaligus.
        Mengembalikan hasil untuk semua label termasuk yang not_found.
        """
        return [self.normalize(label) for label in raw_labels]

    def get_canonical_labels(self, raw_labels: list[str]) -> list[str]:
        """
        Shortcut: mengembalikan hanya label kanonik yang berhasil dinormalisasi.
        Label yang not_found dibuang secara diam-diam (sudah di-log sebagai warning).
        """
        results = self.normalize_batch(raw_labels)
        return [r.canonical for r in results if r.canonical is not None]
