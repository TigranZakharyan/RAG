import tempfile
from pathlib import Path

from fastapi import UploadFile
from docling.document_converter import DocumentConverter

class FileProcessor:
    def __init__(self):
        self.converter = DocumentConverter()

    async def process(self, file: UploadFile) -> str:
        suffix = Path(file.filename or "").suffix

        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            delete=False,
        ) as temp:
            temp_path = Path(temp.name)

            while chunk := await file.read(1024 * 1024):
                temp.write(chunk)

        try:
            result = self.converter.convert(str(temp_path))

            return result.document.export_to_markdown()

        finally:
            temp_path.unlink(missing_ok=True)

file_processor = FileProcessor()