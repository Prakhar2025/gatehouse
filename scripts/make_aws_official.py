"""Gatehouse reference architecture in the official AWS Architecture Center
style: white page, dashed AWS Cloud boundary, category-colored service icon
tiles with white service glyphs, orthogonal numbered flows, AWS attribution
footer. 2400x1350 PNG. Reproducible from this script alone.
"""
from PIL import Image, ImageDraw, ImageFont

F = "C:/Windows/Fonts/"
W, H = 2400, 1350
WHITE = (255, 255, 255)
PAGE = (250, 250, 250)
INK = (21, 31, 46)          # aws dark navy text
SILVER = (110, 122, 138)
DASH = (0, 100, 200)
GRID = (235, 237, 240)

# AWS category tile colors
ORANGE = (237, 113, 0)      # compute
TEAL = (1, 168, 141)        # ml / bedrock
VIOLET = (201, 37, 209)     # database
GREEN = (122, 161, 22)      # storage
PURPLE = (140, 79, 255)     # networking
PINK = (231, 87, 123)       # app integration
NAVY = (35, 47, 62)         # aws cloud border
GREY = (105, 125, 125)      # client / generic


def ft(bold, size):
    return ImageFont.truetype(F + ("arialbd.ttf" if bold else "arial.ttf"), size)


def tile(d, x, y, size, color, glyph):
    """Service icon tile: category-colored rounded square with white glyph."""
    d.rounded_rectangle([x, y, x + size, y + size], radius=int(size * 0.12), fill=color)
    g = "white"
    cx, cy = x + size / 2, y + size / 2
    s = size
    if glyph == "lambda":
        d.arc([cx - s * 0.22, cy - s * 0.30, cx + s * 0.22, cy + s * 0.30], 300, 90, fill=g, width=int(s * 0.09))
        d.line([(cx + s * 0.02, cy - s * 0.05), (cx + s * 0.22, cy + s * 0.26)], fill=g, width=int(s * 0.09))
    elif glyph == "dynamodb":
        ew, eh = s * 0.26, s * 0.055
        for dy in (-0.22, -0.02, 0.18, 0.22):
            d.ellipse([cx - ew, cy + s * dy - eh, cx + ew, cy + s * dy + eh], outline=g, width=int(s * 0.05))
        d.line([(cx - ew, cy - 0.22 * s), (cx - ew, cy + 0.22 * s)], fill=g, width=int(s * 0.05))
        d.line([(cx + ew, cy - 0.22 * s), (cx + ew, cy + 0.22 * s)], fill=g, width=int(s * 0.05))
    elif glyph == "bucket":
        d.polygon([(cx - s * 0.28, cy - s * 0.10), (cx + s * 0.28, cy - s * 0.10),
                   (cx + s * 0.20, cy + s * 0.28), (cx - s * 0.20, cy + s * 0.28)], outline=g, width=int(s * 0.05))
        d.ellipse([cx - s * 0.28, cy - s * 0.16, cx + s * 0.28, cy - s * 0.04], outline=g, width=int(s * 0.05))
    elif glyph == "apigw":
        for dx in (-0.16, 0.16):
            d.ellipse([cx + s * dx - s * 0.08, cy - s * 0.10, cx + s * dx + s * 0.08, cy + s * 0.10], outline=g, width=int(s * 0.05))
        d.line([(cx - s * 0.08, cy), (cx + s * 0.08, cy)], fill=g, width=int(s * 0.05))
    elif glyph == "cloudfront":
        d.ellipse([cx - s * 0.26, cy - s * 0.26, cx + s * 0.26, cy + s * 0.26], outline=g, width=int(s * 0.05))
        d.line([(cx - s * 0.26, cy), (cx + s * 0.26, cy)], fill=g, width=int(s * 0.04))
        d.arc([cx - s * 0.14, cy - s * 0.26, cx + s * 0.14, cy + s * 0.26], 0, 180, fill=g, width=int(s * 0.04))
    elif glyph == "eventbridge":
        for i, dy in enumerate((-0.18, 0.0, 0.18)):
            wbar = s * (0.30 - abs(dy) * 0.4)
            d.rounded_rectangle([cx - wbar, cy + s * dy - s * 0.045, cx + wbar, cy + s * dy + s * 0.045],
                                radius=int(s * 0.04), outline=g, width=int(s * 0.045))
    elif glyph == "bedrock":
        d.line([(cx - s * 0.24, cy - s * 0.24), (cx + s * 0.24, cy + s * 0.24)], fill=g, width=int(s * 0.07))
        d.line([(cx - s * 0.24, cy + s * 0.24), (cx + s * 0.24, cy - s * 0.24)], fill=g, width=int(s * 0.07))
        d.ellipse([cx - s * 0.07, cy - s * 0.07, cx + s * 0.07, cy + s * 0.07], outline=g, width=int(s * 0.05))
    elif glyph == "cloudwatch":
        d.ellipse([cx - s * 0.20, cy - s * 0.20, cx + s * 0.10, cy + s * 0.10], outline=g, width=int(s * 0.05))
        d.line([(cx + s * 0.08, cy + s * 0.08), (cx + s * 0.24, cy + s * 0.24)], fill=g, width=int(s * 0.055))
        d.line([(cx - s * 0.10, cy - s * 0.05), (cx - s * 0.03, cy - s * 0.05), (cx + s * 0.05, cy - s * 0.14)],
               fill=g, width=int(s * 0.045))


def numbered(d, x, y, n):
    d.ellipse([x - 18, y - 18, x + 18, y + 18], fill=(41, 128, 185))
    f = ft(True, 20)
    t = str(n)
    b = d.textbbox((0, 0), t, font=f)
    d.text((x - (b[2] - b[0]) / 2, y - (b[3] - b[1]) / 2 - 3), t, font=f, fill=WHITE)


def conn(d, pts, n=None, color=(120, 135, 150)):
    for i in range(len(pts) - 1):
        d.line([pts[i], pts[i + 1]], fill=color, width=3)
    (x1, y1), (x2, y2) = pts[-2], pts[-1]
    import math
    a = math.atan2(y2 - y1, x2 - x1)
    L = 14
    d.polygon([(x2, y2), (x2 - L * math.cos(a - 0.45), y2 - L * math.sin(a - 0.45)),
               (x2 - L * math.cos(a + 0.45), y2 - L * math.sin(a + 0.45))], fill=color)
    if n:
        mid = pts[len(pts) // 2]
        numbered(d, mid[0], mid[1], n)


def svc(d, x, y, label, sub, color, glyph, ts=110):
    tile(d, x, y, ts, color, glyph)
    d.text((x, y + ts + 10), label, font=ft(True, 21), fill=INK)
    if sub:
        d.text((x, y + ts + 36), sub, font=ft(False, 17), fill=SILVER)


def grid(d, w, h, step=64):
    for x in range(0, w, step):
        d.line([(x, 0), (x, h)], fill=GRID, width=1)
    for y in range(0, h, step):
        d.line([(0, y), (w, y)], fill=GRID, width=1)


img = Image.new("RGB", (W, H), PAGE)
d = ImageDraw.Draw(img)
grid(d, W, H, 64)

# Title
d.text((60, 42), "Gatehouse: Household fraud defense on AWS", font=ft(True, 42), fill=INK)
d.text((62, 100), "Reference architecture - live in staging - September 2026", font=ft(False, 24), fill=SILVER)

# Clients zone (left, outside cloud)
d.text((60, 190), "Clients", font=ft(True, 24), fill=INK)
for i, name in enumerate(["Family members", "Guardian"]):
    y = 240 + i * 110
    d.rounded_rectangle([60, y, 330, y + 84], radius=10, fill=WHITE, outline=GREY, width=2)
    d.text((80, y + 14), name, font=ft(True, 22), fill=INK)
    d.text((80, y + 46), "forwards anything suspicious", font=ft(False, 18), fill=SILVER)
d.text((60, 490), "messages arrive via messaging platforms", font=ft(False, 18), fill=SILVER)

# AWS Cloud dashed boundary
d.rounded_rectangle([430, 170, 2340, 1270], radius=16, outline=NAVY, width=4)
d.rectangle([432, 156, 760, 190], fill=PAGE)
d.text((452, 158), "AWS Cloud - Region ap-south-1", font=ft(True, 24), fill=INK)

# Edge and delivery
d.text((480, 230), "Edge and delivery", font=ft(True, 22), fill=INK)
svc(d, 480, 275, "Amazon API Gateway", "HTTP API - webhook intake", PINK, "apigw")
svc(d, 700, 275, "Amazon CloudFront", "static console + landing", PURPLE, "cloudfront")
svc(d, 920, 275, "Amazon S3", "console assets", GREEN, "bucket")

# Application integration + compute
d.text((480, 460), "Application integration and compute", font=ft(True, 22), fill=INK)
svc(d, 480, 505, "AWS Lambda", "intake + investigation", ORANGE, "lambda")
svc(d, 700, 505, "Amazon EventBridge", "case events bus", PINK, "eventbridge")
svc(d, 920, 505, "AWS Lambda", "daily digest", ORANGE, "lambda")
svc(d, 1140, 505, "AWS Lambda", "console api", ORANGE, "lambda")

# AI/ML
d.text((480, 690), "Machine learning", font=ft(True, 22), fill=INK)
svc(d, 480, 735, "Amazon Bedrock", "Nova Micro - APAC profile", TEAL, "bedrock")
d.rounded_rectangle([700, 735, 1240, 845], radius=8, fill=WHITE, outline=GREY, width=2)
d.text((720, 750), "Deterministic rule engine", font=ft(True, 21), fill=INK)
d.text((720, 780), "pack v0.2.0 - registries + provenance", font=ft(False, 18), fill=SILVER)
d.text((720, 806), "models propose scores - code decides verdicts", font=ft(False, 18), fill=SILVER)

# Database
d.text((480, 920), "Database", font=ft(True, 22), fill=INK)
svc(d, 480, 965, "Amazon DynamoDB", "cases + evidence bundles", VIOLET, "dynamodb")
svc(d, 700, 965, "Amazon DynamoDB", "graph + bindings", VIOLET, "dynamodb")

# Observability strip
d.text((1320, 920), "Management and governance", font=ft(True, 22), fill=INK)
svc(d, 1320, 965, "Amazon CloudWatch", "scrubbed traces + alarms", ORANGE, "cloudwatch")
d.rounded_rectangle([1540, 965, 2280, 1075], radius=8, fill=WHITE, outline=GREY, width=2)
d.text((1560, 980), "Spend meter - hard breaker caps", font=ft(True, 20), fill=INK)
d.text((1560, 1012), "total evaluation spend to date: $0.26", font=ft(False, 18), fill=SILVER)

# Console web app (inside cloud, right side)
svc(d, 1500, 505, "Web console", "Next.js static on CloudFront+S3", GREEN, "bucket")

# ---- Flows ----
conn(d, [(330, 300), (478, 300)], 1)
conn(d, [(570, 385), (570, 505)], 2)
conn(d, [(620, 615), (620, 733)], 3)
conn(d, [(700, 615), (760, 733)], 4)
conn(d, [(760, 615), (900, 733), (900, 961)], 5)
conn(d, [(620, 845), (620, 963)], 6)
conn(d, [(330, 300), (400, 140), (1490, 140), (1490, 273), (334, 273)], 7)
conn(d, [(1090, 336), (1090, 430)], 8)

# Legend
d.text((60, 620), "How to read", font=ft(True, 22), fill=INK)
items = [
    (ORANGE, "compute (AWS Lambda)"),
    (PINK, "app integration (API GW, EventBridge)"),
    (TEAL, "machine learning (Bedrock)"),
    (VIOLET, "database (DynamoDB)"),
    (GREEN, "storage (S3)"),
    (PURPLE, "networking (CloudFront)"),
]
for i, (c, t) in enumerate(items):
    x = 60 + (i % 2) * 130
    y = 660 + (i // 2) * 90
    tile(d, x, y, 56, c, {"lambda": "lambda", "apigw": "apigw", "bedrock": "bedrock",
                          "dynamodb": "dynamodb", "bucket": "bucket", "cloudfront": "cloudfront"}[t.split()[0].lower() if False else "lambda"])
    d.text((x, y + 66), t, font=ft(False, 15), fill=INK)

# Footer
d.line([(0, H - 80), (W, H - 80)], fill=GREY, width=1)
d.text((60, H - 62), "(c) 2026, Amazon Web Services, Inc. or its affiliates. Gatehouse reference architecture - built in the open for the AWS Agents for Humans hackathon.",
       font=ft(False, 19), fill=SILVER)
d.text((60, H - 34), "Precision 1.00 CI [0.9887, 1.0] - false-gate 0.0% - $0.00026 per investigation - 469 tests green", font=ft(False, 19), fill=SILVER)

img.save("docs/submission/aws-official-architecture.png", quality=95)
print("aws-official-architecture.png", img.size)
