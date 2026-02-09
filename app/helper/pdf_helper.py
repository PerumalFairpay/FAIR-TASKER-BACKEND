from weasyprint import HTML
from io import BytesIO
from pypdf import PdfReader, PdfWriter

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
