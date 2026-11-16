"""Filesystem tests use temporary directories, never the configured storage root."""
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import UUID

import pytest

from app.services import storage_service
from app.services.storage_service import LocalStorageService


@pytest.fixture
def storage(tmp_path):
    return LocalStorageService(tmp_path / "storage")


def files(storage):
    return [path for path in storage.root.rglob("*") if path.is_file()]


@pytest.mark.parametrize("extension,content", [
    ("txt", "Hello café".encode()),
    ("md", b"# Notes\nSome text"),
    # Header validation only; this deliberately is not a fully parsed PDF.
    ("pdf", b"%PDF-1.7\nexample"),
    (".TXT", b"Normalized extension"),
])
def test_save_and_read_exact_bytes(storage, extension, content):
    key, size = storage.save(BytesIO(content), 12, extension, len(content))
    assert size == len(content)
    relative = Path(key)
    assert relative.parts[0] == "12"
    assert UUID(relative.stem).version == 4
    assert relative.suffix == "." + extension.lower().lstrip(".")
    assert "\\" not in key
    with storage.open(key) as stream:
        assert stream.read() == content
    assert stream.closed


def test_prepare_creates_directories_but_not_file(storage):
    key, destination = storage.prepare_destination_path(1, "txt")
    assert destination == storage.resolve_storage_key(key)
    assert destination.parent.is_dir()
    assert not destination.exists()


def test_repeated_saves_generate_different_keys(storage):
    first, _ = storage.save(BytesIO(b"same"), 1, "txt", 100)
    second, _ = storage.save(BytesIO(b"same"), 1, "txt", 100)
    assert first != second
    assert len(files(storage)) == 2


@pytest.mark.parametrize("extension,content", [
    ("txt", b""), ("md", b""), ("pdf", b""),
    ("txt", b"\xff\xfe"), ("md", b"\xff"),
    ("txt", b"hello\xe2\x82"), ("md", b"hello\xe2\x82"),
    ("pdf", b"not a PDF"), ("pdf", b"%PDF"),
])
def test_invalid_content_leaves_no_partial_file(storage, extension, content):
    existing_key, _ = storage.save(BytesIO(b"Keep me"), 1, "txt", 100)
    with pytest.raises(ValueError):
        storage.save(BytesIO(content), 1, extension, 1024)
    assert files(storage) == [storage.resolve_storage_key(existing_key)]
    assert storage.resolve_storage_key(existing_key).read_bytes() == b"Keep me"


def test_oversize_after_first_chunk_removes_partial_file(storage):
    content = b"a" * (64 * 1024 + 1)
    with pytest.raises(ValueError, match="size"):
        storage.save(BytesIO(content), 1, "txt", len(content) - 1)
    assert files(storage) == []


@pytest.mark.parametrize("limit", [0, -1])
def test_nonpositive_size_limit_rejected(storage, limit):
    with pytest.raises(ValueError):
        storage.save(BytesIO(b"a"), 1, "txt", limit)
    assert files(storage) == []


@pytest.mark.parametrize("extension", ["exe", "", "txt/../../secret", "docx"])
def test_unsupported_extension_rejected(storage, extension):
    with pytest.raises(ValueError):
        storage.save(BytesIO(b"data"), 1, extension, 100)
    assert files(storage) == []


def test_utf8_character_spanning_chunks_is_valid(storage):
    content = b"a" * (64 * 1024 - 1) + "€".encode()
    key, size = storage.save(BytesIO(content), 1, "txt", len(content))
    assert size == len(content)
    with storage.open(key) as stream:
        assert stream.read() == content


def test_pdf_header_spanning_short_reads(storage):
    class ShortReads(BytesIO):
        def read(self, size=-1):
            return super().read(min(size, 2))

    content = b"%PDF-1.7\nexample"
    key, size = storage.save(ShortReads(content), 1, "pdf", len(content))
    assert size == len(content)
    assert storage.resolve_storage_key(key).read_bytes() == content


def test_stream_failure_removes_partial_file(storage):
    failure = OSError("Read failed")

    class FailingStream:
        reads = 0

        def read(self, size):
            assert size == 64 * 1024
            self.reads += 1
            if self.reads == 1:
                return b"partial contents"
            raise failure

    with pytest.raises(OSError) as error:
        storage.save(FailingStream(), 1, "txt", 1024)
    assert error.value is failure
    assert files(storage) == []


def test_uuid_collision_never_overwrites_or_deletes_existing_file(storage, monkeypatch):
    fixed_uuid = UUID("12345678-1234-4234-8234-123456789abc")
    monkeypatch.setattr(storage_service, "uuid4", lambda: fixed_uuid)
    key, _ = storage.save(BytesIO(b"original"), 1, "txt", 100)
    with pytest.raises(FileExistsError):
        storage.save(BytesIO(b"replacement"), 1, "txt", 100)
    assert storage.resolve_storage_key(key).read_bytes() == b"original"
    assert len(files(storage)) == 1


def test_failed_publication_removes_temporary_file(storage, monkeypatch):
    failure = PermissionError("Publishing denied")
    attempted = []

    def fail_publish(source, destination):
        source, destination = Path(source), Path(destination)
        assert source.parent == destination.parent
        assert source.read_bytes() == b"complete contents"
        assert not destination.exists()
        attempted.append((source, destination))
        raise failure

    monkeypatch.setattr(storage_service.os, "link", fail_publish)
    with pytest.raises(PermissionError) as error:
        storage.save(BytesIO(b"complete contents"), 1, "txt", 100)
    assert error.value is failure
    assert len(attempted) == 1
    assert not attempted[0][0].exists()
    assert not attempted[0][1].exists()
    assert files(storage) == []


def test_final_name_appears_only_after_writing_finishes(storage, monkeypatch):
    fixed_uuid = UUID("12345678-1234-4234-8234-123456789abc")
    monkeypatch.setattr(storage_service, "uuid4", lambda: fixed_uuid)
    destination = storage.root / "1" / f"{fixed_uuid.hex}.txt"
    content = b"a" * (64 * 1024 + 1)

    class ObservedStream(BytesIO):
        def read(self, size=-1):
            assert not destination.exists()
            temporary_files = list(destination.parent.glob(".upload-*.tmp"))
            assert len(temporary_files) == 1
            return super().read(size)

    key, size = storage.save(ObservedStream(content), 1, "txt", len(content))
    assert size == len(content)
    assert storage.resolve_storage_key(key) == destination
    assert destination.read_bytes() == content
    assert files(storage) == [destination]


def test_concurrent_publication_collision_preserves_winning_file(storage, monkeypatch):
    fixed_uuid = UUID("12345678-1234-4234-8234-123456789abc")
    monkeypatch.setattr(storage_service, "uuid4", lambda: fixed_uuid)
    real_link = storage_service.os.link
    ready = Barrier(2, timeout=5)

    def simultaneous_publish(source, destination):
        ready.wait()
        return real_link(source, destination)

    monkeypatch.setattr(storage_service.os, "link", simultaneous_publish)

    def save(content):
        try:
            key, _ = storage.save(BytesIO(content), 1, "txt", 100)
            return key, content
        except FileExistsError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save, [b"first writer", b"second writer"]))
    winners = [result for result in results if result is not None]
    assert len(winners) == 1
    key, content = winners[0]
    destination = storage.resolve_storage_key(key)
    assert destination.read_bytes() == content
    assert files(storage) == [destination]


@pytest.mark.parametrize("key", [
    "../secret.txt", "/secret.txt", "C:/secret.txt", "1/report.pdf",
    "1/../../secret.txt", "1\\" + "a" * 32 + ".txt",
    "0/" + "a" * 32 + ".txt", "1/" + "a" * 32 + ".exe",
])
def test_invalid_keys_rejected_for_resolve_read_and_delete(storage, tmp_path, key):
    outside = tmp_path / "secret.txt"
    outside.write_bytes(b"untouched")
    for operation in (storage.resolve_storage_key, storage.open, storage.delete):
        with pytest.raises(ValueError):
            operation(key)
    assert outside.read_bytes() == b"untouched"


def test_delete_is_repeatable_and_open_missing_file_fails(storage):
    key, _ = storage.save(BytesIO(b"delete me"), 1, "txt", 100)
    storage.delete(key)
    assert not storage.resolve_storage_key(key).exists()
    storage.delete(key)
    with pytest.raises(FileNotFoundError):
        storage.open(key)


@pytest.mark.parametrize("workspace_id", [0, -1])
def test_nonpositive_workspace_id_rejected(storage, workspace_id):
    with pytest.raises(ValueError):
        storage.save(BytesIO(b"data"), workspace_id, "txt", 100)
    assert files(storage) == []


def test_relative_root_rejected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError):
        LocalStorageService(Path("relative-storage"))
    assert not (tmp_path / "relative-storage").exists()
