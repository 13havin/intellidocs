from pathlib import Path
from uuid import uuid4
from typing import BinaryIO
import codecs, re

class LocalStorageService:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        
    def prepare_destination_path(self, workspace_id: int, extension: str) -> tuple[str, Path]:
        extension = extension.lower().lstrip(".")
        if extension not in {"pdf", "txt", "md"}:
            raise ValueError(f"Unsupported file extension: {extension}")
        
        filename = f"{uuid4().hex}.{extension}"
        relative_path = Path(str(workspace_id)) / filename
        destination_path = (self.root / relative_path).resolve()
        
        if not destination_path.is_relative_to(self.root):
            raise ValueError("Destination path is outside the storage root.")
        
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        
        return relative_path.as_posix(), destination_path
    
    def save(self, stream: BinaryIO, workspace_id: int, extension: str, max_size_bytes: int) -> tuple[str, int]:
        if max_size_bytes <= 0:
            raise ValueError("Maximum file size must be a positive integer.")
        
        key, destination_path = self.prepare_destination_path(workspace_id, extension)
        
        total_size = 0
        created = False
        
        extension = extension.lower().lstrip(".")
        
        decoder = (
            codecs.getincrementaldecoder("utf-8")()
            if extension in {"txt", "md"}
            else None
        )
        
        pdf_header = bytearray()
        
        try:
            with destination_path.open("xb") as output:
                created = True
                
                while chunk := stream.read(64 * 1024):
                    total_size += len(chunk)
                    
                    if total_size > max_size_bytes:
                        raise ValueError(f"File size exceeds the maximum allowed size")
                    
                    if decoder is not None:
                        try:
                            decoder.decode(chunk, final=False)
                        except UnicodeDecodeError as exc:
                            raise ValueError(f"Text files must be valid UTF-8 encoded.") from exc
                        
                    if extension == "pdf" and len(pdf_header) < 5:
                        remaining = 5 - len(pdf_header)
                        pdf_header.extend(chunk[:remaining])
                
                    output.write(chunk)
                    
                if total_size == 0:
                    raise ValueError("Empty files are not allowed")
                
                if decoder is not None:
                    try:
                        decoder.decode(b"", final=True)
                    except UnicodeDecodeError as exc:
                        raise ValueError("Text file ends with incomplete UTF-8 data") from exc
                
                if extension == "pdf" and bytes(pdf_header) != b"%PDF-":
                    raise ValueError("File does not have the expected PDF header")
                
        except Exception:
            if created:
                destination_path.unlink(missing_ok=True)
            raise
        
        return key, total_size
    
    def resolve_storage_key(self, storage_key: str) -> Path:
        pattern = r"[1-9][0-9]*/[0-9a-f]{32}\.(pdf|txt|md)"
        
        if re.fullmatch(pattern, storage_key) is None:
            raise ValueError(f"Invalid storage key")
        
        destination = (self.root / storage_key).resolve()
        
        if not destination.is_relative_to(self.root):
            raise ValueError("Storage path is outside the storage root.")
        
        return destination
    
    def open(self, storage_key: str) -> BinaryIO:
        path = self.resolve_storage_key(storage_key)
        return path.open("rb")
    
    def delete(self, storage_key: str) -> None:
        path = self.resolve_storage_key(storage_key)
        path.unlink(missing_ok=True)