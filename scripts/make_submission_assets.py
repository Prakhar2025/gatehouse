"""Generate submission assets: architecture diagram + gallery images.

All numbers are real (docs/eval-results/). Deterministic. Brand system:
warm ink surfaces, bone text, amber accent, verdict hues only as semantics.
"""
from PIL import Image, ImageDraw, ImageFont

INK = (10, 10, 11)
PANEL = (17, 17, 19)
PANEL2 = (22, 22, 25)
BONE = (236, 233, 228)
SILVER = (143, 143, 150)
DIM = (85, 85, 92)
AMBER = (255, 180, 84)
GREEN = (61, 220, 132)
RED = (255, 107, 107)
BLUE = (122, 184, 255)
LINE = (52, 52, 60)
GRID = (28, 28, 32)

F = "C:/Windows/Fonts/"
def font(bold=False, size=28, mono=False, narrow=False):
    if mono:
        return ImageFont.truetype(F + ("consolab.ttf" if bold else "consola.ttf"), size)
    if narrow:
        return ImageFont.truetype(F + ("arialnbd.ttf" if bold else "arialn.ttf"), size)
    return ImageFont.truetype(F + ("arialbd.ttf" if bold else "arial.ttf"), size)


def grid_bg(d, w, h, step=60):
    for x in range(0, w, step):
        d.line([(x, 0), (x, h)], fill=GRID, width=1)
    for y in range(0, h, step):
        d.line([(0, y), (w, y)], fill=GRID, width=1)


def panel(d, box, title=None, accent=None):
    x0, y0, x1, y1 = box
    d.rounded_rectangle(box, radius=14, fill=PANEL, outline=LINE, width=2)
    if title:
        d.text((x0 + 24, y0 + 18), title, font=font(True, 26), fill=BONE)
        d.line([(x0 + 24, y0 + 58), (x1 - 24, y0 + 58)], fill=LINE, width=1)


def arrow(d, p1, p2, color=DIM, width=3):
    d.line([p1, p2], fill=color, width=width)
    import math
    ang = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
    L = 16
    for s in (-1, 1):
        d.line([p2, (p2[0] - L * math.cos(ang - s * 0.45), p2[1] - L * math.sin(ang - s * 0.45))], fill=color, width=width)


def badge(d, xy, n, color=AMBER):
    x, y = xy
    r = 20
    d.ellipse([x - r, y - r, x + r, y + r], fill=color)
    f = font(True, 22, mono=True)
    t = str(n)
    tb = d.textbbox((0, 0), t, font=f)
    d.text((x - (tb[2] - tb[0]) / 2, y - (tb[3] - tb[1]) / 2 - 4), t, font=f, fill=INK)


def kicker(d, xy, text, color=SILVER):
    d.text(xy, text.upper(), font=font(True, 20, mono=True), fill=color)


def footer(d, w, h, left):
    d.rectangle([0, h - 14, w, h], fill=AMBER)
    d.text((48, h - 66), left, font=font(False, 24, mono=True), fill=SILVER)


W, H = 2400, 1350

# ================= ARCHITECTURE (2400x1350) =================
img = Image.new("RGB", (W, H), INK)
d = ImageDraw.Draw(img)
grid_bg(d, W, H)

d.text((60, 46), "Gatehouse", font=font(True, 44), fill=BONE)
d.text((340, 62), "Reference Architecture · AWS ap-south-1 · v1.4.2", font=font(False, 26, mono=True), fill=SILVER)
d.text((W - 700, 62), "Strands Agents SDK · Amazon Bedrock", font=font(False, 24, mono=True), fill=DIM)

# Clients zone
panel(d, (60, 150, 460, 620), None)
kicker(d, (84, 172), "clients")
for i, name in enumerate(["Telegram", "WhatsApp", "Email", "Web console"]):
    y = 220 + i * 78
    d.rounded_rectangle([84, y, 424, y + 58], radius=10, fill=PANEL2, outline=LINE, width=2)
    d.text((104, y + 15), name, font=font(True, 24), fill=BONE)
d.text((84, 540), "family members forward", font=font(False, 20), fill=DIM)
d.text((84, 566), "anything suspicious", font=font(False, 20), fill=DIM)

# Region container
d.rounded_rectangle([520, 150, 2340, 1230], radius=18, fill=(12, 12, 14), outline=(64, 64, 72), width=2)
kicker(d, (548, 170), "aws region · ap-south-1")
d.text((2050, 170), "single-region v1", font=font(False, 20, mono=True), fill=DIM)

# Edge layer
panel(d, (560, 220, 2320, 340), None)
for i, name in enumerate(["Amazon API Gateway", "Amazon CloudFront"]):
    x = 580 + i * 330
    d.rounded_rectangle([x, 252, x + 300, 312], radius=10, fill=PANEL2, outline=LINE, width=2)
    d.text((x + 20, 268), name, font=font(True, 23), fill=BONE)
d.text((580, 320), "HTTP API · webhook intake", font=font(False, 19), fill=DIM)
d.text((910, 320), "console + landing", font=font(False, 19), fill=DIM)

# Compute layer
panel(d, (560, 420, 2320, 630), None)
kicker(d, (584, 450), "compute · aws lambda (serverless)")
lams = [
    ("Intake + Investigation", "fence · triage · verify · graph", AMBER),
    ("Digest", "daily morning summary", None),
    ("Console API", "serves the guardian console", None),
]
for i, (name, sub, acc) in enumerate(lams):
    x = 584 + i * 580
    d.rounded_rectangle([x, 490, x + 540, 610], radius=10, fill=PANEL2, outline=(AMBER if acc else LINE), width=2)
    d.text((x + 22, 508), name, font=font(True, 24), fill=BONE)
    d.text((x + 22, 548), sub, font=font(False, 19), fill=DIM)

# AI layer
panel(d, (560, 650, 2320, 850), None)
kicker(d, (584, 680), "ai layer")
d.rounded_rectangle([584, 716, 1180, 836], radius=10, fill=PANEL2, outline=AMBER, width=2)
d.text((606, 734), "Amazon Bedrock · Nova Micro", font=font(True, 24), fill=BONE)
d.text((606, 772), "APAC inference profile · structured output · triage only", font=font(False, 19), fill=DIM)
d.text((606, 800), "models propose scores · code decides verdicts", font=font(False, 19), fill=SILVER)
d.rounded_rectangle([1220, 716, 1816, 836], radius=10, fill=PANEL2, outline=LINE, width=2)
d.text((1242, 734), "Deterministic rule engine", font=font(True, 24), fill=BONE)
d.text((1242, 772), "pack v0.2.0: issuers · trusted tiers · en+hi lexicons", font=font(False, 19), fill=DIM)
d.text((1242, 800), "provenance on every result · never capped by the model", font=font(False, 19), fill=SILVER)
d.rounded_rectangle([1856, 716, 2312, 836], radius=10, fill=PANEL2, outline=LINE, width=2)
d.text((1878, 734), "Threat graph", font=font(True, 24), fill=BONE)
d.text((1878, 772), "HMAC-keyed identity hashes · cross-household taint", font=font(False, 19), fill=DIM)

# Data layer
panel(d, (560, 880, 2320, 1040), None)
kicker(d, (584, 910), "data")
tables = ["cases", "graph", "bindings + invites"]
for i, t in enumerate(tables):
    x = 584 + i * 400
    d.rounded_rectangle([x, 946, x + 360, 1026], radius=10, fill=PANEL2, outline=LINE, width=2)
    d.text((x + 20, 962), "Amazon DynamoDB", font=font(True, 20), fill=BONE)
    d.text((x + 20, 992), t, font=font(False, 19), fill=SILVER)
d.rounded_rectangle([1816, 946, 2312, 1026], radius=10, fill=PANEL2, outline=LINE, width=2)
d.text((1838, 962), "Amazon S3", font=font(True, 20), fill=BONE)
d.text((1838, 992), "static console + landing", font=font(False, 19), fill=SILVER)

# Async + observability strip
panel(d, (560, 1080, 2320, 1150), None)
d.text((584, 1112), "Amazon EventBridge · case events", font=font(False, 21), fill=SILVER)
d.text((1180, 1112), "Amazon CloudWatch · scrubbed structured traces", font=font(False, 21), fill=SILVER)
d.text((1900, 1112), "Spend meter · hard breaker caps", font=font(False, 21), fill=SILVER)

# Flows: numbered badges with arrows
arrow(d, (430, 300), (560, 300), SILVER)
badge(d, (495, 300), 1)
arrow(d, (860, 312), (860, 430), SILVER); badge(d, (860, 371), 2)
arrow(d, (900, 371), (900, 430), SILVER, 2)
arrow(d, (1124, 494), (1124, 430), SILVER)
arrow(d, (861, 610), (861, 716), AMBER); badge(d, (861, 663), 3, AMBER)
arrow(d, (1300, 560), (900, 716), SILVER); badge(d, (1000, 620), 4)
arrow(d, (1700, 610), (1900, 716), SILVER); badge(d, (1800, 663), 5)
arrow(d, (861, 836), (861, 890), SILVER); badge(d, (861, 863), 6)
arrow(d, (900, 371), (400, 371), DIM, 2)
badge(d, (430, 371), 7)
arrow(d, (700, 1026), (700, 1090), DIM); badge(d, (700, 1058), 8)

d.text((60, 620), "guardian decides", font=font(True, 22), fill=BONE)
d.text((60, 652), "with the evidence", font=font(True, 22), fill=BONE)
d.text((60, 700), "humans hold the", font=font(False, 19), fill=DIM)
d.text((60, 724), "money decisions", font=font(False, 19), fill=DIM)

# Legend
panel(d, (60, 870, 460, 1230), None)
kicker(d, (84, 902), "flow")
legend = [
    (1, "member forwards the suspicious message"),
    (2, "webhook hits the intake lambda"),
    (3, "fence + canary, then triage on bedrock"),
    (4, "claim verification against registries"),
    (5, "identifiers hashed into the threat graph"),
    (6, "guardian composes verdict + bundle"),
    (7, "member reply + guardian escalation card"),
    (8, "daily morning digest to the household"),
]
for i, (n, t) in enumerate(legend):
    y = 940 + i * 36
    badge(d, (104, y + 12), n, AMBER if n in (3, 6) else DIM)
    d.text((140, y), t, font=font(False, 21), fill=BONE)

footer(d, W, H, "LIVE IN STAGING · 480-CASE BENCHMARK · PRECISION 1.00 CI [0.9887-1.0] · FALSE-GATE 0.0% · $0.00026/CASE · ZERO-SPEND DESIGN")
img.save("docs/submission/architecture.png", quality=95)
print("architecture.png", img.size)
