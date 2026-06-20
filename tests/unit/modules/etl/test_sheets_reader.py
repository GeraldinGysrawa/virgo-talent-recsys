import pytest
from unittest.mock import MagicMock, patch

from src.modules.etl.sheets_reader import SheetsReader


@patch('src.modules.etl.sheets_reader.Credentials.from_service_account_file')
@patch('src.modules.etl.sheets_reader.gspread.authorize')
def test_sheets_reader_fetch_all_success(mock_authorize, mock_creds):
    # Setup mocks
    mock_client = MagicMock()
    mock_authorize.return_value = mock_client
    
    mock_spreadsheet = MagicMock()
    mock_client.open_by_key.return_value = mock_spreadsheet
    
    mock_worksheet = MagicMock()
    mock_spreadsheet.sheet1 = mock_worksheet
    
    # Mock return data for get_all_records
    mock_worksheet.get_all_records.return_value = [
        {
            "No.": 1,
            "Nama Lengkap": "Budi Santoso",
            "NIP": "001234",
            "Jenis Penempatan": "Jakarta",
            "Concern Perbankan": "Ya",
            "Teknologi": "React, Node.js",
            "Pengalaman": 3,
            "Project": "Dashboard",
            "start_date": "01/01/2023",
            "end_date": "01/12/2023",
            "Pendidikan": "S1",
            "status_penugasan": "idle"
        },
        {
            "No.": 2,
            "Nama Lengkap": "Kosong NIP",
            "NIP": "   ", # Should be skipped
            "Jenis Penempatan": "Remote",
        },
        {
            "No.": 3,
            "Nama Lengkap": "Andi",
            "NIP": "054321",
            "Teknologi": "Vue"
        }
    ]
    
    reader = SheetsReader(
        credentials_path="dummy_path.json",
        spreadsheet_id="dummy_id"
    )
    
    results = reader.fetch_all()
    
    # Verify results
    assert len(results) == 2
    
    # Verify mapping and leading zeros
    assert results[0]["nip"] == "001234"
    assert results[0]["nama_lengkap"] == "Budi Santoso"
    assert results[0]["jenis_penempatan"] == "Jakarta"
    assert results[0]["concern_perbankan"] == "Ya"
    
    assert results[1]["nip"] == "054321"
    assert results[1]["nama_lengkap"] == "Andi"


@patch('src.modules.etl.sheets_reader.Credentials.from_service_account_file')
@patch('src.modules.etl.sheets_reader.gspread.authorize')
def test_sheets_reader_worksheet_name_parameter(mock_authorize, mock_creds):
    # Memastikan param worksheet_name memaksa reader memanggil spreadsheet.worksheet()
    mock_client = MagicMock()
    mock_authorize.return_value = mock_client
    mock_spreadsheet = MagicMock()
    mock_client.open_by_key.return_value = mock_spreadsheet
    mock_worksheet = MagicMock()
    mock_spreadsheet.worksheet.return_value = mock_worksheet
    mock_worksheet.get_all_records.return_value = []
    
    reader = SheetsReader(
        credentials_path="dummy_path.json",
        spreadsheet_id="dummy_id",
        worksheet_name="Data Talent"
    )
    
    reader.fetch_all()
    
    mock_spreadsheet.worksheet.assert_called_once_with("Data Talent")
