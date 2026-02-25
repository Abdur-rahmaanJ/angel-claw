import os
import json
import base64
import logging
from typing import Optional
from angel_claw.skills.manager import skill
from angel_claw.config import settings
from PIL import Image

logger = logging.getLogger("angel-claw-file-handler")

UPLOAD_DIR = os.path.join(os.getcwd(), ".angelclaw", "uploads")


def _get_upload_dir() -> str:
    """Get or create upload directory."""
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)
    return UPLOAD_DIR


def _save_file(file_data: str, filename: str) -> str:
    """Save a base64-encoded file."""
    upload_dir = _get_upload_dir()

    # Sanitize filename
    safe_name = os.path.basename(filename)
    filepath = os.path.join(upload_dir, safe_name)

    # Handle base64 data
    if "," in file_data:
        # Data URL format: data:image/png;base64,...
        header, data = file_data.split(",", 1)
        with open(filepath, "wb") as f:
            f.write(base64.b64decode(data))
    else:
        # Raw base64
        with open(filepath, "wb") as f:
            f.write(base64.b64decode(file_data))

    return filepath


def _get_file_info(filepath: str) -> dict:
    """Get file information."""
    stat = os.stat(filepath)
    return {
        "filename": os.path.basename(filepath),
        "size_bytes": stat.st_size,
        "size_formatted": _format_size(stat.st_size),
        "created": stat.st_ctime,
        "modified": stat.st_mtime,
    }


def _format_size(size: int) -> str:
    """Format file size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


@skill
def save_file(file_data: str, filename: str) -> str:
    """
    Saves a file from base64 data.
    - file_data: Base64-encoded file data (can be data URL like data:image/png;base64,...)
    - filename: Name to save the file as
    """
    try:
        filepath = _save_file(file_data, filename)
        info = _get_file_info(filepath)

        return f"✅ File saved: {info['filename']} ({info['size_formatted']})\nPath: {filepath}"
    except Exception as e:
        return f"Error saving file: {e}"


@skill
def get_file_info(filename: str) -> str:
    """
    Gets information about a file.
    - filename: Name of the file in .angelclaw/uploads/
    """
    upload_dir = _get_upload_dir()
    filepath = os.path.join(upload_dir, filename)

    if not os.path.exists(filepath):
        return f"Error: File '{filename}' not found. Upload it first with save_file()."

    try:
        info = _get_file_info(filepath)

        lines = [
            f"## File Info: {info['filename']}",
            f"- Size: {info['size_formatted']}",
            f"- Created: {info['created']}",
            f"- Modified: {info['modified']}",
        ]

        # Try to get image dimensions
        if filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
            try:
                with Image.open(filepath) as img:
                    lines.append(f"- Dimensions: {img.size[0]} x {img.size[1]} px")
                    lines.append(f"- Format: {img.format}")
            except:
                pass

        return "\n".join(lines)

    except Exception as e:
        return f"Error: {e}"


@skill
def list_uploaded_files() -> str:
    """
    Lists all uploaded files.
    """
    upload_dir = _get_upload_dir()

    if not os.path.exists(upload_dir):
        return "No files uploaded yet."

    files = os.listdir(upload_dir)

    if not files:
        return "No files uploaded yet."

    lines = ["## Uploaded Files\n"]

    for f in sorted(files):
        filepath = os.path.join(upload_dir, f)
        info = _get_file_info(filepath)
        lines.append(f"- {info['filename']} ({info['size_formatted']})")

    return "\n".join(lines)


@skill
def delete_file(filename: str) -> str:
    """
    Deletes an uploaded file.
    - filename: Name of the file to delete
    """
    upload_dir = _get_upload_dir()
    filepath = os.path.join(upload_dir, filename)

    if not os.path.exists(filepath):
        return f"Error: File '{filename}' not found."

    try:
        os.remove(filepath)
        return f"🗑️ Deleted: {filename}"
    except Exception as e:
        return f"Error deleting file: {e}"


@skill
def extract_pdf_text(filename: str) -> str:
    """
    Extracts text from a PDF file.
    - filename: Name of the PDF file in .angelclaw/uploads/
    """
    upload_dir = _get_upload_dir()
    filepath = os.path.join(upload_dir, filename)

    if not os.path.exists(filepath):
        return f"Error: File '{filename}' not found. Upload it first with save_file()."

    if not filename.lower().endswith(".pdf"):
        return f"Error: '{filename}' is not a PDF file."

    try:
        import PyPDF2

        text_parts = []
        with open(filepath, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text.strip():
                    text_parts.append(f"--- Page {i + 1} ---\n{text}")

        if not text_parts:
            return "No text could be extracted from this PDF."

        full_text = "\n\n".join(text_parts)

        # Limit to first 15000 chars for LLM context
        if len(full_text) > 15000:
            full_text = full_text[:15000] + "\n\n[... Truncated ...]"

        return f"## Extracted Text from {filename}\n\n{full_text}"

    except ImportError:
        return "Error: PyPDF2 not installed. Run: pip install PyPDF2"
    except Exception as e:
        return f"Error extracting PDF: {e}"


@skill
def analyze_image(
    filename: str, question: str = "Describe this image in detail."
) -> str:
    """
    Analyzes an image using AI vision.
    - filename: Name of the image file in .angelclaw/uploads/
    - question: What to ask about the image
    """
    upload_dir = _get_upload_dir()
    filepath = os.path.join(upload_dir, filename)

    if not os.path.exists(filepath):
        return f"Error: File '{filename}' not found. Upload it first with save_file()."

    # Check if it's an image
    if not filename.lower().endswith(
        (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")
    ):
        return f"Error: '{filename}' is not a supported image format."

    try:
        # Read and encode image
        with open(filepath, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        # Try to use litellm with vision
        import litellm

        # Determine model - use one that supports vision
        model = settings.model
        if "gpt-4" not in model and "vision" not in model.lower():
            # Try default vision model
            model = "openai/gpt-4o"  # has vision

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_data}"},
                    },
                ],
            }
        ]

        response = litellm.completion(
            model=model,
            messages=messages,
            api_key=settings.api_key,
            api_base=settings.api_base,
        )

        return f"## Image Analysis\n\n{response.choices[0].message.content}"

    except ImportError:
        return "Error: litellm not available for vision analysis."
    except Exception as e:
        return f"Error analyzing image: {e}"


@skill
def extract_text_from_image(filename: str) -> str:
    """
    Extracts text from an image using OCR.
    - filename: Name of the image file in .angelclaw/uploads/
    """
    upload_dir = _get_upload_dir()
    filepath = os.path.join(upload_dir, filename)

    if not os.path.exists(filepath):
        return f"Error: File '{filename}' not found. Upload it first with save_file()."

    if not filename.lower().endswith(
        (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")
    ):
        return f"Error: '{filename}' is not an image."

    try:
        import pytesseract

        text = pytesseract.image_to_string(Image.open(filepath))

        if not text.strip():
            return "No text found in image."

        return f"## Extracted Text\n\n{text}"

    except ImportError:
        return "Error: pytesseract not installed. Run: pip install pytesseract pillow"
    except Exception as e:
        return f"Error extracting text: {e}"
