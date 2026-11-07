"""Genera los íconos PNG de la app web (pantalla de inicio del iPhone y Android).

Mismo diseño que el icono de la bandeja (`tray_image` en launcher.py), pero a sangre completa:
iOS y Android redondean las esquinas por su cuenta.

    uv run --extra desktop python scripts/make-icons.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

GREEN = "#0f6b4f"
PUBLIC = Path(__file__).resolve().parents[1] / "frontend" / "public"
SIZES = {"apple-touch-icon.png": 180, "icon-192.png": 192, "icon-512.png": 512}


def icon(size: int) -> Image.Image:
    big = 1024  # se dibuja grande y se reduce para bordes suaves
    img = Image.new("RGB", (big, big), GREEN)
    draw = ImageDraw.Draw(img)
    # La "M" del icono de la bandeja (64 px), centrada y con margen para la máscara de Android.
    points = [(14, 46), (14, 20), (23, 34), (32, 20), (41, 34), (50, 20), (50, 46)]
    scale, offset = big / 64 * 0.72, big * 0.14
    draw.line(
        [(x * scale + offset, y * scale + offset) for x, y in points],
        fill="white",
        width=round(5 * scale),
        joint="curve",
    )
    return img.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    for name, size in SIZES.items():
        icon(size).save(PUBLIC / name, optimize=True)
        print(f"{name}: {size}x{size}")


if __name__ == "__main__":
    main()
