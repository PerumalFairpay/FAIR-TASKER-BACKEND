from weasyprint import HTML
from io import BytesIO
from pypdf import PdfReader, PdfWriter
import base64
import mimetypes


def image_to_base64(image_path: str) -> str:
    """
    Reads an image file and returns a base64 data URI string.
    e.g. 'data:image/png;base64,iVBORw0...'
    """
    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type:
        mime_type = "image/png"  # fallback
    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"

def generate_pdf_from_html(html_content: str, base_url: str = "") -> bytes:
    """
    Generates PDF bytes from HTML content.
    """
    pdf_buffer = BytesIO()
    HTML(string=html_content, base_url=base_url).write_pdf(pdf_buffer)
    pdf_buffer.seek(0)
    return pdf_buffer.read()

def encrypt_pdf(pdf_bytes: bytes, password: str) -> bytes:
    """
    Encrypts PDF bytes with a password using AES-128 (default in pypdf).
    """
    if not password:
        return pdf_bytes

    reader = PdfReader(BytesIO(pdf_bytes))
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    # Encrypt with the user password
    writer.encrypt(user_password=password, owner_password=password)
    
    output_buffer = BytesIO()
    writer.write(output_buffer)
    output_buffer.seek(0)
    return output_buffer.read()

def decrypt_pdf(pdf_bytes: bytes, password: str) -> bytes:
    """
    Decrypts PDF bytes using a password.
    """
    if not password:
        return pdf_bytes

    reader = PdfReader(BytesIO(pdf_bytes))
    if reader.is_encrypted:
        reader.decrypt(password)

    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)

    output_buffer = BytesIO()
    writer.write(output_buffer)
    output_buffer.seek(0)
    return output_buffer.read()
