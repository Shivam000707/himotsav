"""Generate the 7 clean + 7 damaged synthetic reports for Ramesh ji and labels.json."""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

SYNTH_DIR = Path(__file__).resolve().parent
IMAGES_DIR = SYNTH_DIR / "images"
FONTS_DIR = SYNTH_DIR / "fonts"

WIDTH = 1240
HEIGHT = 1754

THEMES = {
    "sunrise": {"header_bg": (247, 226, 203), "accent": (180, 95, 14)},
    "valley": {"header_bg": (217, 230, 246), "accent": (29, 58, 99)},
    "city": {"header_bg": (220, 239, 226), "accent": (11, 110, 102)},
    "dra": {"header_bg": (255, 255, 255), "accent": (29, 58, 99)},
    "drb": {"header_bg": (255, 255, 255), "accent": (29, 58, 99)},
}


def load_font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in candidates:
        for base in [FONTS_DIR, Path("C:/Windows/Fonts")]:
            p = base / name
            if p.exists():
                try:
                    return ImageFont.truetype(str(p), size=size)
                except OSError:
                    pass
    return ImageFont.load_default()


def render_paper(paper: dict, patient: dict, out_path: Path) -> None:
    img = Image.new("RGB", (WIDTH, HEIGHT), (255, 254, 250))
    draw = ImageDraw.Draw(img)

    f_title = load_font(["NotoSans-Bold.ttf", "arialbd.ttf", "segoeui.ttf"], 42)
    f_sub = load_font(["NotoSans-Regular.ttf", "arial.ttf", "segoeui.ttf"], 26)
    f_body = load_font(["NotoSans-Regular.ttf", "arial.ttf", "segoeui.ttf"], 30)
    f_bold = load_font(["NotoSans-Bold.ttf", "arialbd.ttf", "segoeui.ttf"], 30)
    f_hand = load_font(["Kalam-Regular.ttf", "segoepr.ttf", "comic.ttf", "arial.ttf"], 34)

    theme = THEMES.get(paper.get("theme", "dra"), THEMES["dra"])
    is_rx = paper["kind"] == "rx"

    # Header band
    draw.rectangle([(0, 0), (WIDTH, 180)], fill=theme["header_bg"])
    draw.line([(0, 180), (WIDTH, 180)], fill=(210, 204, 192), width=3)
    draw.text((60, 48), paper["org"], fill=theme["accent"], font=f_title)
    doc_type = "PRESCRIPTION" if is_rx else "PATHOLOGY LAB REPORT"
    draw.text((60, 112), f"{doc_type}  |  Synthetic Demo Data", fill=(70, 82, 96), font=f_sub)

    # Patient meta
    draw.text(
        (60, 225),
        f"Patient: {patient['display_name']}   |   Age/Sex: {patient['age']} / {patient['gender']}",
        fill=(31, 41, 51),
        font=f_bold,
    )
    draw.text((880, 225), f"Date: {paper['date']}", fill=(31, 41, 51), font=f_bold)
    draw.line([(60, 285), (WIDTH - 60, 285)], fill=(210, 204, 192), width=2)

    y = 340
    if is_rx:
        draw.text((60, y), "Rx", fill=theme["accent"], font=f_title)
        y += 80
        for row in paper["rows"]:
            if row.get("smudge_strength"):
                # Draw Amaryl, then smudged '1', then mg + frequency
                draw.text((80, y), "Tab. Amaryl", fill=(31, 41, 51), font=f_hand)
                smudge_layer = Image.new("RGB", (90, 60), (255, 254, 250))
                s_draw = ImageDraw.Draw(smudge_layer)
                s_draw.text((15, 8), "1", fill=(165, 165, 165), font=f_hand)
                smudge_layer = smudge_layer.filter(ImageFilter.GaussianBlur(radius=3.2))
                img.paste(smudge_layer, (295, y - 4))
                draw.text((355, y), f"mg    {row['value']}", fill=(31, 41, 51), font=f_hand)
            else:
                draw.text((80, y), f"{row['label']}    {row['value']}", fill=(31, 41, 51), font=f_hand)
            y += 95
    else:
        # Table header
        draw.rectangle([(60, y), (WIDTH - 60, y + 60)], fill=(242, 244, 247))
        draw.text((80, y + 14), "Test", fill=(71, 88, 109), font=f_bold)
        draw.text((700, y + 14), "Result", fill=(71, 88, 109), font=f_bold)
        draw.text((940, y + 14), "Unit", fill=(71, 88, 109), font=f_bold)
        y += 80
        for row in paper["rows"]:
            draw.text((80, y), row["label"], fill=(31, 41, 51), font=f_body)
            draw.text((700, y), row["value"], fill=(31, 41, 51), font=f_bold)
            draw.text((940, y), row.get("unit", ""), fill=(71, 88, 109), font=f_body)
            draw.line([(60, y + 58), (WIDTH - 60, y + 58)], fill=(230, 226, 218), width=1)
            y += 85

    draw.text(
        (60, HEIGHT - 90),
        "MediKiosk-DM Synthetic Test Document - Not a Real Patient Record",
        fill=(130, 140, 152),
        font=f_sub,
    )
    img.save(out_path, format="PNG")


def make_damaged(clean_path: Path, damaged_path: Path, angle: float) -> None:
    img = Image.open(clean_path).convert("RGB")
    img = img.rotate(angle, resample=Image.BICUBIC, fillcolor=(235, 232, 225))
    img = img.filter(ImageFilter.GaussianBlur(radius=1.2))
    img = ImageEnhance.Brightness(img).enhance(0.75)
    img.save(damaged_path, format="JPEG", quality=55)


def main() -> None:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    data = json.loads((SYNTH_DIR / "ramesh.json").read_text(encoding="utf-8"))
    patient = data["patient"]
    papers = data["papers"]

    labels = []
    angles = [-2.5, 2.8, -1.8, 3.0, -2.2, 1.9, -2.9]

    for idx, paper in enumerate(papers):
        clean_path = IMAGES_DIR / f"{paper['id']}.png"
        damaged_path = IMAGES_DIR / f"{paper['id']}_damaged.jpg"
        render_paper(paper, patient, clean_path)
        make_damaged(clean_path, damaged_path, angles[idx % len(angles)])

        for variant, img_path in [("clean", clean_path), ("damaged", damaged_path)]:
            labels.append(
                {
                    "id": f"{paper['id']}_{variant}",
                    "paper_id": paper["id"],
                    "variant": variant,
                    "image_path": str(img_path.relative_to(SYNTH_DIR.parent.parent)).replace("\\", "/"),
                    "kind": paper["kind"],
                    "org": paper["org"],
                    "date": paper["date"],
                    "rows": paper["rows"],
                }
            )

    (SYNTH_DIR / "labels.json").write_text(json.dumps(labels, indent=2), encoding="utf-8")
    print(f"Generated {len(labels)} images and labels.json in {SYNTH_DIR}")


def main_personas() -> None:
    """Clean images only for the extra demo patients in personas.json (Ramesh's files are left untouched)."""
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    data = json.loads((SYNTH_DIR / "personas.json").read_text(encoding="utf-8"))
    n = 0
    for persona in data["personas"]:
        for paper in persona["papers"]:
            render_paper(paper, persona["patient"], IMAGES_DIR / f"{paper['id']}.png")
            n += 1
    print(f"Generated {n} persona images in {IMAGES_DIR}")


if __name__ == "__main__":
    import sys

    if "--personas" in sys.argv:
        main_personas()
    else:
        main()
