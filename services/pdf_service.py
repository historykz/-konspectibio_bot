import os
import logging
from PIL import Image
import img2pdf
from config import SUBMISSIONS_DIR

logger = logging.getLogger(__name__)


async def photos_to_pdf(photo_paths: list[str], student_telegram_id: int) -> str | None:
    """Convert a list of image paths to a single PDF and save it."""
    try:
        valid_paths = []
        for p in photo_paths:
            if os.path.exists(p):
                valid_paths.append(p)
            else:
                logger.warning(f"Photo not found: {p}")

        if not valid_paths:
            logger.error("No valid photos to convert")
            return None

        # Convert all images to RGB JPEG for img2pdf compatibility
        converted = []
        for idx, p in enumerate(valid_paths):
            try:
                img = Image.open(p).convert("RGB")
                converted_path = p + "_converted.jpg"
                img.save(converted_path, "JPEG", quality=90)
                converted.append(converted_path)
            except Exception as e:
                logger.error(f"Failed to convert image {p}: {e}")

        if not converted:
            return None

        pdf_filename = f"submission_{student_telegram_id}_{int(__import__('time').time())}.pdf"
        pdf_path = os.path.join(SUBMISSIONS_DIR, pdf_filename)

        with open(pdf_path, "wb") as f:
            f.write(img2pdf.convert(converted))

        # Clean up converted temps
        for p in converted:
            try:
                os.remove(p)
            except Exception:
                pass

        logger.info(f"PDF created: {pdf_path}")
        return pdf_path

    except Exception as e:
        logger.error(f"PDF creation error: {e}", exc_info=True)
        return None
