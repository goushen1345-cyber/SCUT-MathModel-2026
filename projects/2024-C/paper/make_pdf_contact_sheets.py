from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parents[1] / "paper" / "qa_pdf"
pages = sorted(root.glob("page-*.png"))
font = ImageFont.truetype(r"C:\Windows\Fonts\simhei.ttf", 24)
for group_no in range(0, len(pages), 4):
    selected = pages[group_no:group_no + 4]
    thumb_w = 850
    thumb_h = 1203
    sheet = Image.new("RGB", (thumb_w * 2 + 60, thumb_h * 2 + 100), "#d7dde4")
    draw = ImageDraw.Draw(sheet)
    for idx, path in enumerate(selected):
        im = Image.open(path).convert("RGB")
        im.thumbnail((thumb_w, thumb_h - 34), Image.Resampling.LANCZOS)
        x = 20 + (idx % 2) * (thumb_w + 20)
        y = 20 + (idx // 2) * (thumb_h + 20)
        sheet.paste(im, (x + (thumb_w - im.width)//2, y + 32))
        draw.text((x + 5, y), path.stem, font=font, fill="#17202b")
    out = root / f"contact_{group_no//4 + 1:02d}.png"
    sheet.save(out)
    print(out)
