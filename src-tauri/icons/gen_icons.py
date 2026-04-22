import asyncio, io
from pathlib import Path
from PIL import Image

ICONS_DIR = Path(__file__).parent
SVG_CONTENT = open(ICONS_DIR / "postpilot.svg", "r", encoding="utf-8").read()

ICO_SIZES = [256, 64, 48, 32, 24, 16]


async def render(size):
    from playwright.async_api import async_playwright

    rs = max(size * 4, 1024)
    svg = SVG_CONTENT.replace('width="1024"', f'width="{rs}"').replace(
        'height="1024"', f'height="{rs}"'
    )
    html = (
        "<!DOCTYPE html><html><head><style>"
        "*{margin:0;padding:0}"
        f"body{{width:{rs}px;height:{rs}px;overflow:hidden;background:transparent}}"
        f"</style></head><body>{svg}</body></html>"
    )

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            viewport={"width": rs, "height": rs}, device_scale_factor=1
        )
        await page.set_content(html, wait_until="networkidle")
        await page.wait_for_timeout(300)
        shot = await page.screenshot(
            type="png",
            omit_background=True,
            clip={"x": 0, "y": 0, "width": rs, "height": rs},
        )
        await browser.close()

    img = Image.open(io.BytesIO(shot)).convert("RGBA")
    if img.size[0] != size:
        img = img.resize((size, size), Image.LANCZOS)
    return img


async def main():
    targets = [
        ("icon.png", 512),
        ("32x32.png", 32),
        ("128x128.png", 128),
        ("128x128@2x.png", 256),
    ]
    for name, size in targets:
        img = await render(size)
        img.save(ICONS_DIR / name)
        print(f"  {name} ({size}x{size})")

    imgs = []
    for s in ICO_SIZES:
        imgs.append(await render(s))
    imgs[0].save(
        ICONS_DIR / "icon.ico",
        format="ICO",
        append_images=imgs[1:],
        sizes=[(s, s) for s in ICO_SIZES],
    )
    print("  icon.ico")
    print("Done!")


asyncio.run(main())
