import base64
import io
from pathlib import Path

import pandas as pd
from PIL import Image
from pypdf import PdfReader
from docx import Document


SUPPORTED_FILE_TYPES = [
    "pdf",
    "docx",
    "txt",
    "csv",
    "xlsx",
    "png",
    "jpg",
    "jpeg",
    "webp",
]


IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


def get_extension(filename: str) -> str:
    return Path(filename).suffix.lower().replace(".", "")


def truncate_text(text: str, max_chars: int = 25_000) -> str:
    if not text:
        return ""

    if len(text) <= max_chars:
        return text

    return (
        text[:max_chars]
        + "\n\n[Texto truncado por límite de tamaño. "
        + f"Se mostraron los primeros {max_chars} caracteres.]"
    )


def extract_text_from_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))

    pages_text = []

    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages_text.append(f"\n--- Página {i} ---\n{text}")

    return "\n".join(pages_text).strip()


def extract_text_from_docx(file_bytes: bytes) -> str:
    document = Document(io.BytesIO(file_bytes))

    paragraphs = [
        paragraph.text.strip()
        for paragraph in document.paragraphs
        if paragraph.text.strip()
    ]

    return "\n".join(paragraphs).strip()


def extract_text_from_txt(file_bytes: bytes) -> str:
    try:
        return file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return file_bytes.decode("latin-1", errors="ignore")


def extract_text_from_csv(file_bytes: bytes, max_rows: int = 100) -> str:
    buffer = io.BytesIO(file_bytes)

    try:
        df = pd.read_csv(buffer, nrows=max_rows)
    except UnicodeDecodeError:
        buffer = io.BytesIO(file_bytes)
        df = pd.read_csv(buffer, nrows=max_rows, encoding="latin-1")

    return df.to_csv(index=False)


def extract_text_from_xlsx(file_bytes: bytes, max_rows_per_sheet: int = 80) -> str:
    buffer = io.BytesIO(file_bytes)

    sheets = pd.read_excel(
        buffer,
        sheet_name=None,
        nrows=max_rows_per_sheet,
    )

    output = []

    for sheet_name, df in sheets.items():
        output.append(f"\n--- Hoja: {sheet_name} ---\n")
        output.append(df.to_csv(index=False))

    return "\n".join(output).strip()


def image_to_data_url(
    file_bytes: bytes,
    max_side: int = 1600,
    quality: int = 85,
) -> str:
    """
    Convierte una imagen a data URL en memoria.
    La redimensiona para evitar mandar imágenes demasiado grandes al modelo.
    No guarda nada en disco.
    """

    image = Image.open(io.BytesIO(file_bytes))

    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    image.thumbnail((max_side, max_side))

    output_buffer = io.BytesIO()
    image.save(output_buffer, format="JPEG", quality=quality)

    encoded = base64.b64encode(output_buffer.getvalue()).decode("utf-8")

    return f"data:image/jpeg;base64,{encoded}"


def process_uploaded_files(uploaded_files, max_total_text_chars: int = 40_000):
    """
    Procesa archivos cargados desde Streamlit sin escribirlos en disco.

    Returns:
        dict con:
        - documents_context: texto extraído de PDF/DOCX/TXT/CSV/XLSX
        - image_parts: lista compatible con OpenAI multimodal
        - files_summary: resumen de archivos procesados
        - errors: errores encontrados
    """

    documents_chunks = []
    image_parts = []
    files_summary = []
    errors = []

    if not uploaded_files:
        return {
            "documents_context": "",
            "image_parts": [],
            "files_summary": [],
            "errors": [],
        }

    for uploaded_file in uploaded_files:
        filename = uploaded_file.name
        extension = get_extension(filename)
        file_bytes = uploaded_file.getvalue()

        try:
            if extension == "pdf":
                text = extract_text_from_pdf(file_bytes)
                text = truncate_text(text, max_chars=20_000)

                documents_chunks.append(
                    f"\n\n===== Archivo PDF: {filename} =====\n{text}"
                )

                files_summary.append(
                    {
                        "filename": filename,
                        "type": "pdf",
                        "status": "texto extraído",
                    }
                )

            elif extension == "docx":
                text = extract_text_from_docx(file_bytes)
                text = truncate_text(text, max_chars=20_000)

                documents_chunks.append(
                    f"\n\n===== Archivo Word: {filename} =====\n{text}"
                )

                files_summary.append(
                    {
                        "filename": filename,
                        "type": "docx",
                        "status": "texto extraído",
                    }
                )

            elif extension == "txt":
                text = extract_text_from_txt(file_bytes)
                text = truncate_text(text, max_chars=20_000)

                documents_chunks.append(
                    f"\n\n===== Archivo TXT: {filename} =====\n{text}"
                )

                files_summary.append(
                    {
                        "filename": filename,
                        "type": "txt",
                        "status": "texto extraído",
                    }
                )

            elif extension == "csv":
                text = extract_text_from_csv(file_bytes)
                text = truncate_text(text, max_chars=15_000)

                documents_chunks.append(
                    f"\n\n===== Archivo CSV: {filename} =====\n{text}"
                )

                files_summary.append(
                    {
                        "filename": filename,
                        "type": "csv",
                        "status": "tabla leída parcialmente",
                    }
                )

            elif extension == "xlsx":
                text = extract_text_from_xlsx(file_bytes)
                text = truncate_text(text, max_chars=20_000)

                documents_chunks.append(
                    f"\n\n===== Archivo Excel: {filename} =====\n{text}"
                )

                files_summary.append(
                    {
                        "filename": filename,
                        "type": "xlsx",
                        "status": "hojas leídas parcialmente",
                    }
                )

            elif extension in IMAGE_EXTENSIONS:
                data_url = image_to_data_url(file_bytes)

                image_parts.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": data_url,
                        },
                    }
                )

                files_summary.append(
                    {
                        "filename": filename,
                        "type": extension,
                        "status": "imagen preparada para modelo multimodal",
                    }
                )

            else:
                errors.append(
                    {
                        "filename": filename,
                        "error": f"Tipo de archivo no soportado: {extension}",
                    }
                )

        except Exception as e:
            errors.append(
                {
                    "filename": filename,
                    "error": str(e),
                }
            )

    documents_context = "\n".join(documents_chunks)
    documents_context = truncate_text(
        documents_context,
        max_chars=max_total_text_chars,
    )

    return {
        "documents_context": documents_context,
        "image_parts": image_parts,
        "files_summary": files_summary,
        "errors": errors,
    }