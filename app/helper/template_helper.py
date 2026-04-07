import os
from jinja2 import Environment
from app.helper.pdf_helper import image_to_base64

# Resolve assets and templates directories relative to this file's location
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "../assets")
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "../templates")


def render_nda_template(context: dict) -> str:
    """
    Loads nda_form.html, injects base64 images from app/assets/ + dynamic
    NDA data from `context`, and returns the fully rendered HTML string.

    Expected context keys:
        - employee_name (str)
        - employee_address (str)
        - residential_address (str)
        - date (str, formatted)
        - token (str)
        - role (str, optional)
        - signature_data (str | None, optional — base64 signature image)
        - request (dict, optional — full NDA request object)
    """
    template_path = os.path.join(TEMPLATES_DIR, "nda_form.html")
    with open(template_path, "r", encoding="utf-8") as f:
        raw_html = f.read()

    # Inject asset images as base64 data URIs at render-time
    context["watermark_base64"] = image_to_base64(os.path.join(ASSETS_DIR, "watermark.png"))
    context["header_base64"] = image_to_base64(os.path.join(ASSETS_DIR, "header.png"))
    context["footer_base64"] = image_to_base64(os.path.join(ASSETS_DIR, "footer.png"))
    context["company_signature_base64"] = image_to_base64(os.path.join(ASSETS_DIR, "company_signature.png"))


    env = Environment()
    return env.from_string(raw_html).render(**context)
