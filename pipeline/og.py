"""Draw the social preview card, docs/og.png (1200x630), from data/derived/metrics.json.

    python3 -m pipeline.og

Optional: needs Pillow and the IBM Plex fonts (fonts-ibm-plex). It is not part
of build.py; the PNG it writes is committed so link previews work.
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "og.png")
FONTS = "/usr/share/fonts/truetype/ibm-plex/"
W, H = 1200, 630
PAGE, INK, INK2, INK3, RULE = (18, 19, 17), (238, 235, 226), (189, 185, 173), (134, 130, 117), (47, 48, 43)
BLUE, GOOD, BAD, WARN = (91, 132, 240), (67, 163, 90), (224, 103, 93), (217, 165, 32)


def font(name, size):
    from PIL import ImageFont
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def main():
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        sys.exit("needs Pillow: pip install pillow")
    m = json.load(open(os.path.join(ROOT, "data", "derived", "metrics.json")))
    s = m["meta"]["subject"]
    share90 = m["trailing"]["share"][s]
    week = m["stability"]["latest_share"]
    s30 = next((x["share"] for x in m["sensitivity"] if x["days"] == 30), None)
    call = m["call"]["call"]
    img = Image.new("RGB", (W, H), PAGE)
    d = ImageDraw.Draw(img)
    mono, monob = font("IBMPlexMono-Regular.ttf", 20), font("IBMPlexMono-Medium.ttf", 20)
    d.text((64, 52), "SHARE", font=monob, fill=INK)
    d.text((64 + d.textlength("SHARE", font=monob), 52), "/", font=monob, fill=BLUE)
    d.text((64 + d.textlength("SHARE/", font=monob), 52), "SHIFT", font=monob, fill=INK)
    d.text((W - 64, 52), "INVESTMENT THESIS · NEAR", font=mono, fill=INK3, anchor="ra")
    d.line([(64, 92), (W - 64, 92)], fill=INK2, width=1)

    serif, serif_i = font("IBMPlexSerif-Medium.ttf", 54), font("IBMPlexSerif-MediumItalic.ttf", 54)
    d.text((64, 128), "NEAR Intents leads the native-swap", font=serif, fill=INK)
    d.text((64, 196), "venues, but ", font=serif, fill=INK)
    d.text((64 + d.textlength("venues, but ", font=serif), 196), "too little reaches", font=serif_i, fill=BLUE)
    d.text((64, 264), "the NEAR token yet.", font=serif_i, fill=BLUE)

    # weekly share, with the 50% and 40% lines
    wk = [r["share"][s] for r in m["weekly"] if r["share"].get(s) is not None]
    x0, x1, y0, y1 = 700, W - 64, 340, 530
    pts = [(x0 + (x1 - x0) * i / (len(wk) - 1), y1 - (y1 - y0) * v) for i, v in enumerate(wk)]
    d.polygon(pts + [(x1, y1), (x0, y1)], fill=(30, 36, 52))
    for v, col in ((0.5, GOOD), (0.4, BAD)):
        y = y1 - (y1 - y0) * v
        for x in range(x0, x1, 12):
            d.line([(x, y), (min(x + 6, x1), y)], fill=col, width=2)
    d.line(pts, fill=BLUE, width=4, joint="curve")
    d.ellipse([pts[-1][0] - 7, pts[-1][1] - 7, pts[-1][0] + 7, pts[-1][1] + 7], fill=BLUE, outline=PAGE, width=3)
    d.line([(x0, y1), (x1, y1)], fill=INK3, width=1)
    small = font("IBMPlexMono-Regular.ttf", 16)
    d.text((x0, y1 + 12), "Intents share by week, %s to %s" % (m["weekly"][0]["week"][:7], m["weekly"][-1]["week"][:7]),
           font=small, fill=INK3)

    big, lab = font("IBMPlexSerif-Regular.ttf", 64), font("IBMPlexSans-Regular.ttf", 19)
    cols = [("%d%%" % round(100 * share90), "share, 90 days", INK),
            ("%d%%" % round(100 * s30) if s30 is not None else "n/a", "30 days", INK),
            ("%d%%" % round(100 * week), "latest week", INK)]
    x = 64
    for val, text, col in cols:
        d.text((x, 372), val, font=big, fill=col)
        d.text((x, 450), text, font=lab, fill=INK2)
        x += 205
    word = {"WATCH": ("Watch", WARN), "ACCUMULATE": ("Accumulate", GOOD), "AVOID": ("Avoid", BAD)}[call]
    d.text((64, 500), "CALL", font=small, fill=INK3)
    d.text((64, 522), word[0], font=font("IBMPlexSerif-SemiBold.ttf", 44), fill=word[1])
    d.text((64 + d.textlength(word[0], font=font("IBMPlexSerif-SemiBold.ttf", 44)) + 18, 540),
           "not buy, until buybacks cover half of new NEAR", font=lab, fill=INK2)
    d.line([(64, H - 44), (W - 64, H - 44)], fill=RULE, width=1)
    d.text((64, H - 34), "n0ctr1.github.io/share-shift · every number rebuilt from public data", font=small, fill=INK3)
    img.save(OUT, optimize=True)
    print("wrote %s" % os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    main()
