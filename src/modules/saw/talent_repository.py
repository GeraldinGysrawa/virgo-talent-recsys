# =============================================================
# src/modules/saw/talent_repository.py
# Modul SAW — Increment 3: Simple Additive Weighting
#
# Tanggung Jawab:
#   Akses data talenta dari Neo4j (GRASP Information Expert).
#   Satu-satunya titik di modul SAW yang berinteraksi langsung
#   dengan database — seluruh detail Cypher dan mapping record
#   berhenti di sini.
#
# Catatan:
#   - Bersifat read-only; tidak ada operasi tulis ke Neo4j.
#   - Diinstansiasi oleh caller (router / orchestrator) lalu
#     diinjeksikan ke SAWService via constructor.
# =============================================================

from __future__ import annotations

from loguru import logger
from neo4j import Driver

from src.modules.saw.schemas import TalentProfile


class TalentRepository:
    """
    Repository akses data talenta dari Neo4j (GRASP Information Expert).

    Bertanggung jawab atas seluruh detail Cypher query dan mapping
    record Neo4j → domain object ``TalentProfile``. SAWService tidak
    perlu mengetahui struktur graph maupun tipe driver yang dipakai.

    Parameters
    ----------
    driver : neo4j.Driver
        Neo4j driver instance (dari app.state).
    database : str
        Nama database Neo4j (default: ``"neo4j"``).
    """

    _QUERY = """
        MATCH (t:Talent)
        WHERE t.nip IN $nip_list
        OPTIONAL MATCH (t)-[:PREFERS_PLACEMENT]->(p:Placement)
        RETURN t.nip               AS nip,
               t.namaLengkap       AS nama_lengkap,
               t.statusPenugasan   AS ketersediaan,
               t.pendidikan        AS pendidikan,
               t.pengalamanTahun   AS pengalaman_tahun,
               t.concernPerbankan  AS concern_perbankan,
               collect(p.namaLokasi) AS lokasi_penempatan
    """

    def __init__(self, driver: Driver, database: str = "neo4j") -> None:
        self._driver = driver
        self._database = database

    # ----------------------------------------------------------
    # Public interface
    # ----------------------------------------------------------

    def get_by_nips(self, nip_list: list[str]) -> list[TalentProfile]:
        """
        Mengambil profil talenta dari Neo4j berdasarkan daftar NIP.

        Parameters
        ----------
        nip_list : list[str]
            Daftar NIP yang akan di-query. List kosong mengembalikan
            list kosong tanpa mengeksekusi query ke database.

        Returns
        -------
        list[TalentProfile]
            Profil talenta yang ditemukan. NIP yang tidak ada di Neo4j
            akan di-skip dengan warning log.
        """
        if not nip_list:
            return []

        profiles: list[TalentProfile] = []

        with self._driver.session(database=self._database) as session:
            result = session.run(self._QUERY, nip_list=nip_list)

            for record in result:
                nip = record["nip"]
                if nip is None:
                    continue

                profiles.append(self._map_record(record))

        not_found = set(nip_list) - {p.nip for p in profiles}
        if not_found:
            logger.warning(
                f"TalentRepository: {len(not_found)} NIP tidak ditemukan di Neo4j: "
                f"{sorted(not_found)[:5]}{'...' if len(not_found) > 5 else ''}"
            )

        return profiles

    # ----------------------------------------------------------
    # Private — mapping record → domain object
    # ----------------------------------------------------------

    @staticmethod
    def _map_record(record: object) -> TalentProfile:
        """Memetakan satu Neo4j record ke TalentProfile."""
        pengalaman_raw = record["pengalaman_tahun"]
        pengalaman = float(pengalaman_raw) if pengalaman_raw is not None else 0.0

        concern_raw = record["concern_perbankan"]
        concern = bool(concern_raw) if concern_raw is not None else False

        ketersediaan_raw = record["ketersediaan"]
        ketersediaan = (
            str(ketersediaan_raw).strip().lower() if ketersediaan_raw else "idle"
        )

        lokasi_raw = record["lokasi_penempatan"]
        lokasi = [loc for loc in lokasi_raw if loc is not None] if lokasi_raw else []

        return TalentProfile(
            nip=record["nip"],
            nama_lengkap=record["nama_lengkap"] or record["nip"],
            ketersediaan=ketersediaan,
            pendidikan=record["pendidikan"],
            pengalaman_tahun=pengalaman,
            lokasi_penempatan=lokasi,
            concern_perbankan=concern,
        )
