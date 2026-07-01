from services.upload_service import _determine_status
from utils.validators import ALLOWED_EXTENSIONS, ALLOWED_MIME_TYPES


def test_upload_accepts_only_xlsx_extension():
    assert ALLOWED_EXTENSIONS == {".xlsx"}


def test_upload_accepts_only_xlsx_mime_type():
    assert ALLOWED_MIME_TYPES == {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    }


def test_determine_status_partial_when_some_sheets_skipped_or_partial():
    assert _determine_status(all_success=False, any_success=True) == "partial"


def test_determine_status_skipped_when_no_sheet_inserted_rows():
    assert _determine_status(all_success=False, any_success=False) == "skipped"
