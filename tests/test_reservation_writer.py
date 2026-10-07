import pytest

from mcp_server.reservation_writer import InvalidReservationDataError, write_reservation_record


def test_write_reservation_record_creates_file_with_correct_format(tmp_path):
    file_path = tmp_path / "reservations.txt"
    result = write_reservation_record(
        name="Jane Doe", car_number="ABC123", period="9am -> 11am",
        approval_time="2025-01-10T09:05:00", file_path=str(file_path),
    )
    assert result["status"] == "written"
    assert file_path.read_text().strip() == "Jane Doe | ABC123 | 9am -> 11am | 2025-01-10T09:05:00"


def test_write_reservation_record_appends_without_overwriting(tmp_path):
    file_path = tmp_path / "reservations.txt"
    write_reservation_record("Jane Doe", "ABC123", "9am -> 11am", "t1", file_path=str(file_path))
    write_reservation_record("John Smith", "XYZ999", "1pm -> 3pm", "t2", file_path=str(file_path))

    lines = file_path.read_text().strip().splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("Jane Doe")
    assert lines[1].startswith("John Smith")


def test_write_reservation_record_rejects_pipe_character_injection(tmp_path):
    file_path = tmp_path / "reservations.txt"
    with pytest.raises(InvalidReservationDataError):
        write_reservation_record("Jane | FAKE ENTRY", "ABC123", "9am -> 11am", "t1", file_path=str(file_path))


def test_write_reservation_record_rejects_empty_field(tmp_path):
    file_path = tmp_path / "reservations.txt"
    with pytest.raises(InvalidReservationDataError):
        write_reservation_record("", "ABC123", "9am -> 11am", "t1", file_path=str(file_path))


def test_write_reservation_record_rejects_path_traversal(tmp_path, monkeypatch):
    from mcp_server.config import mcp_settings

    monkeypatch.setattr(mcp_settings, "OUTPUT_DIR", str(tmp_path / "allowed"))
    traversal_path = str(tmp_path / "allowed" / ".." / "escaped.txt")

    with pytest.raises(InvalidReservationDataError):
        write_reservation_record("Jane Doe", "ABC123", "9am -> 11am", "t1", file_path=traversal_path)


def test_write_reservation_record_auto_fills_approval_time_when_omitted(tmp_path):
    file_path = tmp_path / "reservations.txt"
    write_reservation_record("Jane Doe", "ABC123", "9am -> 11am", file_path=str(file_path))
    parts = [p.strip() for p in file_path.read_text().strip().split("|")]
    assert len(parts) == 4
    assert parts[3]