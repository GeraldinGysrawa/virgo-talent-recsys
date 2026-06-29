# =============================================================
# tests/unit/test_neo4j_writer.py
# WB-ETL-04 — Neo4jWriter
#
# Titik keputusan kritis:
#   - write_batch() sukses → WriteResult(success=True)
#   - Exception di transaksi → WriteResult(success=False, message berisi error)
#   - Skill tanpa URI di skill_uri_map → di-skip (tidak error)
#   - write_batch() dengan project_nama → _merge_project_and_rel dipanggil
#   - close() memanggil driver.close()
#
# Dependency mock: Neo4j driver (MagicMock) — tidak ada Bolt call nyata.
# GraphDatabase.driver di-patch agar Neo4jWriter.__init__ tidak menyentuh DB.
# =============================================================

from unittest.mock import MagicMock, patch

import pytest

from src.modules.etl.neo4j_writer import Neo4jWriter, WriteResult
from src.modules.etl.transformer import TalentRecord


# ----------------------------------------------------------
# Helper
# ----------------------------------------------------------

def _record(**overrides) -> TalentRecord:
    base = dict(
        nip="001",
        nama_lengkap="Andi Saputra",
        pengalaman_tahun=3.0,
        concern_perbankan=False,
        jenis_penempatan=["Bandung"],
        skill_labels=["Python"],
        skill_raw=["Python"],
        skill_not_found=[],
        project_nama=None,
        start_date=None,
        end_date=None,
        pendidikan="S1",
        status_penugasan="idle",
    )
    base.update(overrides)
    return TalentRecord(**base)


@pytest.fixture
def writer_with_mock():
    """Neo4jWriter dengan driver di-mock — tidak ada koneksi DB nyata."""
    with patch("src.modules.etl.neo4j_writer.GraphDatabase.driver") as mock_factory:
        mock_driver = MagicMock()
        mock_factory.return_value = mock_driver
        writer = Neo4jWriter(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="password",
        )
        yield writer, mock_driver


def _setup_successful_session(mock_driver: MagicMock) -> tuple[MagicMock, MagicMock]:
    """Setup session + transaction mock untuk simulasi write sukses."""
    mock_session = MagicMock()
    mock_tx = MagicMock()
    mock_session.begin_transaction.return_value.__enter__ = MagicMock(return_value=mock_tx)
    mock_session.begin_transaction.return_value.__exit__ = MagicMock(return_value=False)
    mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
    return mock_session, mock_tx


# ===========================================================
# Tests
# ===========================================================

class TestWriteBatchSuccess:
    def test_single_record_returns_success(self, writer_with_mock):
        writer, mock_driver = writer_with_mock
        _setup_successful_session(mock_driver)

        results = writer.write_batch(
            [_record()],
            skill_uri_map={"Python": "http://padepokan79.com/ontology#Python"},
        )
        assert len(results) == 1
        assert results[0].success is True
        assert results[0].nip == "001"

    def test_multiple_records_all_succeed(self, writer_with_mock):
        writer, mock_driver = writer_with_mock
        _setup_successful_session(mock_driver)

        records = [_record(nip=str(i)) for i in range(3)]
        results = writer.write_batch(records, skill_uri_map={})
        assert all(r.success for r in results)
        assert len(results) == 3

    def test_success_message_is_ok(self, writer_with_mock):
        writer, mock_driver = writer_with_mock
        _setup_successful_session(mock_driver)

        results = writer.write_batch([_record()], skill_uri_map={})
        assert results[0].message == "OK"

    def test_write_batch_empty_records_returns_empty(self, writer_with_mock):
        writer, mock_driver = writer_with_mock
        results = writer.write_batch([], skill_uri_map={})
        assert results == []


class TestWriteBatchFailure:
    def test_exception_returns_failed_result(self, writer_with_mock):
        writer, mock_driver = writer_with_mock
        mock_session = MagicMock()
        mock_session.begin_transaction.side_effect = Exception("Connection refused")
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        results = writer.write_batch([_record()], skill_uri_map={})
        assert results[0].success is False

    def test_exception_message_captured_in_result(self, writer_with_mock):
        writer, mock_driver = writer_with_mock
        mock_session = MagicMock()
        mock_session.begin_transaction.side_effect = Exception("timeout")
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        results = writer.write_batch([_record()], skill_uri_map={})
        assert "timeout" in results[0].message

    def test_one_failed_does_not_prevent_others(self, writer_with_mock):
        """Satu record gagal tidak menghentikan pemrosesan record berikutnya."""
        writer, mock_driver = writer_with_mock

        mock_session = MagicMock()
        mock_tx_ok = MagicMock()

        # Context manager untuk transaksi sukses
        mock_tx_ctx_ok = MagicMock()
        mock_tx_ctx_ok.__enter__ = MagicMock(return_value=mock_tx_ok)
        mock_tx_ctx_ok.__exit__ = MagicMock(return_value=False)

        # Context manager untuk transaksi gagal (begin_transaction gagal)
        mock_tx_ctx_fail = MagicMock()
        mock_tx_ctx_fail.__enter__.side_effect = Exception("fail")

        # begin_transaction dipanggil bergantian: gagal dulu, baru sukses
        tx_call_count = [0]
        def begin_tx_side_effect():
            if tx_call_count[0] == 0:
                tx_call_count[0] += 1
                return mock_tx_ctx_fail
            else:
                tx_call_count[0] += 1
                return mock_tx_ctx_ok

        mock_session.begin_transaction.side_effect = begin_tx_side_effect

        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        records = [_record(nip="001"), _record(nip="002")]
        results = writer.write_batch(records, skill_uri_map={})
        assert len(results) == 2
        assert results[0].success is False
        assert results[1].success is True


class TestWriteBatchSkillHandling:
    def test_skill_without_uri_in_map_is_skipped(self, writer_with_mock):
        """Skill tidak ada di skill_uri_map tidak menyebabkan error."""
        writer, mock_driver = writer_with_mock
        mock_session, mock_tx = _setup_successful_session(mock_driver)

        results = writer.write_batch(
            [_record(skill_labels=["Python", "UnknownSkill"])],
            skill_uri_map={},  # kosong — semua skill di-skip
        )
        assert results[0].success is True

    def test_skill_with_uri_triggers_cypher_run(self, writer_with_mock):
        """Skill dengan URI di map harus menjalankan Cypher."""
        writer, mock_driver = writer_with_mock
        mock_session, mock_tx = _setup_successful_session(mock_driver)

        writer.write_batch(
            [_record(skill_labels=["Python"])],
            skill_uri_map={"Python": "http://padepokan79.com/ontology#Python"},
        )
        # mock_tx.run harus dipanggil (talent node + placement + skill)
        assert mock_tx.run.called


class TestWriteBatchWithProject:
    def test_record_with_project_succeeds(self, writer_with_mock):
        writer, mock_driver = writer_with_mock
        _setup_successful_session(mock_driver)

        record = _record(
            project_nama="Project Alpha",
            start_date="2024-01-01",
            end_date="2024-06-30",
        )
        results = writer.write_batch([record], skill_uri_map={})
        assert results[0].success is True


class TestClose:
    def test_close_calls_driver_close(self, writer_with_mock):
        writer, mock_driver = writer_with_mock
        writer.close()
        mock_driver.close.assert_called_once()
