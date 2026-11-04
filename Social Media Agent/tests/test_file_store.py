import os

from file_store import write_atomically


def test_file_is_written_with_its_folder_and_private_permissions(tmp_path):
    path = tmp_path / "new-folder" / "data.json"

    write_atomically(path, b"content")

    assert path.read_bytes() == b"content"
    assert os.stat(path).st_mode & 0o777 == 0o600
    assert os.stat(path.parent).st_mode & 0o777 == 0o700


def test_existing_file_is_replaced_and_no_temporary_file_is_left(tmp_path):
    path = tmp_path / "data.json"
    path.write_bytes(b"old")

    write_atomically(path, b"new")

    assert path.read_bytes() == b"new"
    assert [file.name for file in tmp_path.iterdir()] == ["data.json"]
