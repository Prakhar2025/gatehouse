"""Render the required AWS architecture diagram, enterprise document style.

AWS solution-architecture conventions: services as cards with category
chips, grouped containers (client, AWS cloud region), orthogonal connectors
with numbered flow badges, legend, title block. 2400x1350 PNG.
"""
from PIL import Image, ImageDraw, ImageFont

INK = (10, 10, 11)
PANEL = (17, 17, 19)
CARD = (24, 24, 28)
BONE = (236, 233, 228)
SILVER = (143, 143, 150)
DIM = (90, 90, 98)
AMBER = (255, 180, 84)
GREEN = (61, 220, 132)
RED = (255, 107, 107)
BLUE = (122, 184, 255)
LINE = (60, 60, 68)
GRID = (26, 26, 30)

# AWS service-category chip colors
C_CLIENT = (146, 146, 153)
C_INTEG = (231, 87, 123)     # application integration (pink)
C_COMPUTE = (237, 113, 0)    # compute (orange)
C_AI = (1, 168, 141)         # machine learning (teal)
C_DB = (201, 37, 209)        # database (violet)
C_STORE = (122, 161, 22)     # storage (green)
C_NET = (140, 79, 255)       # networking (purple)
C_MGMT = (61, 220, 132)      # management/observability

F = "C:/Windows/Fonts/"


def F_(bold=True, size=26, mono=False):
    if mono:
        return ImageFont.truetype(F + ("consolab.ttf" if bold else "consola.ttf"), size)
    return ImageFont.truetype(F + ("arialbd.ttf" if bold else "arial.ttf"), size)


def grid(d, w, h, step=64):
    for x in range(0, w, step):
        d.line([(x, 0), (x, h)], fill=GRID, width=1)
    for y in range(0, h, step):
        d.line([(0, y), (w, y)], fill=GRID, width=1)


def chip_box(d, x, y, w, h, category, name, sub="", dark=True):
    """AWS-style service card: colored category chip, name, optional sub."""
    d.rounded_rectangle([x, y, x + w, y + h], radius=8, fill=CARD, outline=LINE, width=2)
    d.rectangle([x, y + 6, x + 6, y + h - 6], fill=category)
    d.text((x + 20, y + 12), name, font=F_(True, 24), fill=BONE)
    if sub:
        d.text((x + 20, y + 46), sub, font=F_(False, 18), fill=SILVER)
    return (x, y, x + w, y + h)


def container(d, x, y, w, h, label, color=None):
    d.rounded_rectangle([x, y, x + w, y + h], radius=14, outline=LINE, width=2)
    if label:
        d.text((x + 20, y + 12), label.upper(), font=F_(True, 19, mono=True), fill=SILVER)


def hline(d, x1, x2, y, color=DIM, w=3):
    d.line([(x1, y), (x2, y)], fill=color, width=w)


def vline(d, x, y1, y2, color=DIM, w=3):
    d.line([(x, y1), (x, y2)], fill=color, width=w)


def badge(d, x, y, n, color=AMBER):
    r = 19
    d.ellipse([x - r, y - r, x + r, y + r], fill=color)
    f = F_(True, 20, mono=True)
    t = str(n)
    b = d.textbbox((0, 0), t, font=f)
    d.text((x - (b[2] - b[0]) / 2, y - (b[3] - b[1]) / 2 - 3), t, font=f, fill=INK)


def arrow_head(d, x, y, direction, color=DIM):
    s = 9
    if direction == "right":
        d.polygon([(x, y), (x - s, y - s), (x - s, y + s)], fill=color)
    elif direction == "down":
        d.polygon([(x, y), (x - s, y - s), (x + s, y - s)], fill=color)


W, H = 2400, 1350
img = Image.new("RGB", (W, H), INK)
d = ImageDraw.Draw(img)
grid(d, W, H)

# Title block
d.text((60, 40), "Gatehouse", font=F_(True, 40), fill=BONE)
d.text((268, 58), "Household fraud defense - reference architecture", font=F_(False, 24), fill=SILVER)
d.text((W - 860, 58), "AWS ap-south-1 - live in staging - Sep 2026", font=F_(False, 22, mono=True), fill=DIM)

# ---- Clients container (outside cloud) ----
container(d, 50, 150, 320, 420, "clients")
clients = [
    ("Telegram", "primary channel", C_CLIENT),
    ("WhatsApp", "flag-gated", C_CLIENT),
    ("Email intake", "SES", C_CLIENT),
    ("Web console", "guardian", (255, 180, 84)),
]
for i, (name, sub, c) in enumerate(clients):
    chip_box(d, 74, 205 + i * 90, 272, 66, c, name, sub)

# ---- AWS Cloud region container ----
container(d, 430, 130, 1920, 1140, "aws cloud - region ap-south-1")

# Edge & delivery
container(d, 460, 190, 1860, 180, "edge and delivery", C_NET)
chip_box(d, 490, 236, 340, 100, C_NET, "Amazon API Gateway", "HTTP API - webhook intake")
chip_box(d, 890, 236, 300, 100, C_NET, "Amazon CloudFront", "static console + landing")
chip_box(d, 1250, 236, 330, 100, C_COMPUTE, "AWS Lambda", "console api")
chip_box(d, 1640, 236, 330, 100, C_STORE, "Amazon S3", "console assets")

# Application layer
container(d, 460, 420, 1860, 320, "application and agents", C_INTEG)
chip_box(d, 490, 470, 380, 110, C_COMPUTE, "AWS Lambda", "intake + investigation", )
chip_box(d, 930, 470, 380, 110, C_INTEG, "Amazon EventBridge", "case events bus")
chip_box(d, 1370, 470, 380, 110, C_COMPUTE, "AWS Lambda", "daily digest")
chip_box(d, 1810, 470, 460, 110, C_COMPUTE, "AWS Lambda", "console api (reads/writes)")

# AI layer
container(d, 460, 780, 1860, 200, "ai and decisioning", C_AI)
chip_box(d, 490, 830, 430, 110, C_AI, "Amazon Bedrock", "Nova Micro, APAC profile - triage")
chip_box(d, 980, 830, 430, 110, C_AI, "Deterministic rule engine", "pack v0.2.0 - provenance")
chip_box(d, 1470, 830, 380, 110, C_DB, "Threat graph", "HMAC-keyed - taint")

# Database layer
container(d, 460, 1020, 1860, 200, "data", C_DB)
chip_box(d, 490, 1070, 400, 110, C_DB, "Amazon DynamoDB", "cases + evidence bundles")
chip_box(d, 950, 1070, 400, 110, C_DB, "Amazon DynamoDB", "graph + bindings + invites")
chip_box(d, 1410, 1070, 400, 110, C_STORE, "Amazon S3", "long-tail storage")

# Observability strip
container(d, 460, 1200, 1860, 55, None, C_MGMT)
d.text((490, 1220), "Amazon CloudWatch - scrubbed structured traces - spend meter with hard breaker caps",
       font=F_(False, 21), fill=SILVER)

# ---- Connectors (orthogonal, numbered) ----
# 1 clients -> APIGW webhook intake
hline(d, 346, 490, 286, DIM); arrow_head(d, 490, 286, "right"); badge(d, 420, 262, 1)
# 2 APIGW -> intake lambda (down)
vline(d, 660, 336, 470, DIM); arrow_head(d, 660, 470, "down"); badge(d, 660, 402, 2)
# intake -> eventbridge -> digest
hline(d, 870, 930, 525, DIM); arrow_head(d, 930, 525, "right")
hline(d, 1310, 1370, 525, DIM); arrow_head(d, 1370, 525, "right")
# 3 intake -> bedrock
vline(d, 660, 580, 830, DIM); arrow_head(d, 660, 830, "down"); badge(d, 660, 700, 3)
# 4 intake -> rule engine
hline(d, 870, 980, 600, DIM); vline(d, 980, 600, 830, DIM); arrow_head(d, 980, 830, "down"); badge(d, 1050, 700, 4)
# 5 intake -> graph
hline(d, 870, 1660, 630, DIM); vline(d, 1660, 630, 830, DIM); arrow_head(d, 1660, 830, "down"); badge(d, 1730, 700, 5)
# 6 decisioning -> data
vline(d, 660, 940, 1070, DIM); arrow_head(d, 660, 1070, "down"); badge(d, 660, 1000, 6)
vline(d, 1180, 940, 1070, DIM); arrow_head(d, 1180, 1070, "down")
# console api lambda -> dynamo (right side corridor)
vline(d, 2050, 336, 1130, DIM); hline(d, 1890, 2050, 1130, DIM); arrow_head(d, 1890, 1130, "left")
# 7 guardian replies back to clients (corridor x370-430)
hline(d, 490, 420, 525, DIM); vline(d, 420, 525, 380, DIM); hline(d, 420, 346, 380, DIM); arrow_head(d, 346, 380, "left")
badge(d, 420, 455, 7)
# 8 cloudfront -> S3 static assets (corridor y378)
vline(d, 1020, 336, 378, DIM); hline(d, 1020, 1745, 378, DIM); vline(d, 1745, 378, 336, DIM); arrow_head(d, 1745, 336, "up")
badge(d, 1745, 378, 8)

# Legend
container(d, 50, 620, 330, 420, "flow")
legend = [
    (1, "member forwards"),
    (2, "webhook intake"),
    (3, "bedrock triage"),
    (4, "claim verification"),
    (5, "graph correlation"),
    (6, "bundle persisted"),
    (7, "replies + escalation"),
    (8, "static assets served"),
]
for i, (n, t) in enumerate(legend):
    badge(d, 92, 690 + i * 46, n)
    d.text((126, 676 + i * 46), t, font=F_(False, 22), fill=BONE)

container(d, 50, 1070, 330, 170, "doctrine")
d.text((74, 1112), "models propose.", font=F_(True, 24), fill=BONE)
d.text((74, 1144), "code decides.", font=F_(True, 24), fill=AMBER)
d.text((74, 1180), "silence is the default.", font=F_(False, 21), fill=SILVER)
d.text((74, 1206), "evidence on every verdict.", font=F_(False, 21), fill=SILVER)

# Footer
d.rectangle([0, H - 12, W, H], fill=AMBER)
d.text((60, H - 62), "Live in staging - 480-case benchmark - precision 1.00 CI [0.9887, 1.0] - false-gate 0.0% - $0.00026/case - zero-spend design",
       font=F_(False, 22, mono=True), fill=SILVER)

img.save("docs/submission/architecture.png")
print("architecture.png rendered", img.size)
