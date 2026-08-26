"""Seeded full benchmark set generator (doc 07 section 2.1).

Produces the full 600-case adversarial benchmark: ten doc-07 strata mapped
onto typed strata, both languages, three difficulty tiers, split 480 dev /
120 sealed hold-out. Deterministic under fixed seeds: same seed, byte-stable
case list.

Split discipline (doc 07): both splits draw from the SAME template pools under
DIFFERENT seeds, so the hold-out tests generalization rather than novelty.
Templates are slot-filled (amounts, VPAs, domains, reference ids) from
per-case seeded draws. Cross-split text overlap is made STRUCTURALLY
impossible: every message embeds a reference token drawn from a disjoint
range (dev 10000-49999, hold-out 50000-99999), and a runtime assertion
re-verifies zero overlap whenever both splits exist together. The hold-out
is generated lazily in memory only; nothing writes it to disk.

Sourcing rules honored (doc 07): URLs use reserved-example domains only
(no live lookalike registration, ever); scripts paraphrase public pattern
libraries (GASA types, I4C advisories) at multiple literacy levels.
"""

from __future__ import annotations

import random

from gatehouse.evaluation.schemas import EvalCase

DEV_SEED = 4207
HOLDOUT_SEED = 9411
FULL_SET_SIZE = 600
DEV_SET_SIZE = 480
HOLDOUT_SET_SIZE = 120

# doc 07 section 2.1 row -> typed strata. Sums to exactly 600. Public because
# it IS the quota contract tests pin against.
FULL_COUNTS: dict[str, int] = {
    "kyc_scam": 90,
    "digital_arrest": 60,
    "investment": 70,
    "upi_collect_fraud": 60,
    "lottery": 40,
    "courier_scam": 40,
    "job_task_scam": 40,
    # doc row "OTP / impersonation-of-relative" (40) splits evenly:
    "relative_impersonation": 20,
    "otp_forward": 20,
    # doc row "legitimate-but-scary" (80) splits by surface:
    "legit_bank_offer": 30,
    "govt_notice_legit": 25,
    "delivery_update": 25,
    # doc row "benign noise" (80):
    "family_chatter": 35,
    "newsletter_promo": 35,
    "govt_legit_trap": 10,
}
assert sum(FULL_COUNTS.values()) == FULL_SET_SIZE


def _split_counts(total_per_stratum: dict[str, int], holdout: bool) -> dict[str, int]:
    """80/20 per-stratum split; exact because every count divides by five."""
    out: dict[str, int] = {}
    for name, n in total_per_stratum.items():
        if n % 5 != 0:
            raise ValueError(f"stratum {name}: count {n} not divisible by 5")
        out[name] = n // 5 if holdout else n - n // 5
    return out


# --- slot pools -------------------------------------------------------------
# Reserved-example scam domains, never registered (doc 07 sourcing rules).
# Two renderings: plain (exercises the live extraction + FAIL path) and
# bracketed (defanged display form, extraction-invisible by design).
_BAD_DOMAINS_PLAIN = (
    "sbi-kyc-update.top",
    "rbi-notice.site",
    "hdfc-verify.xyz",
    "paytm-kyc.info",
    "icici-alert.top",
    "upi-refund.site",
    "fedex-redelivery.top",
    "dhl-pay.xyz",
    "task-earn.info",
)
_AMOUNTS = ("2,000", "5,000", "8,000", "15,000", "25,000", "50,000", "75,000")
_OTPS = tuple(f"{n:06d}" for n in (449210, 883214, 771063, 512904, 908317))
_VPAS = (
    "fraudcare@upi[.]top",
    "quickrefund@ybl[.]top",
    "paynow123@okaxis[.]top",
    "verifykyc@paytm[.]top",
)
_CITIES = ("Nagpur", "Pune", "Indore", "Jaipur", "Lucknow", "Patna")


def _fill(template: str, rng: random.Random, ref: str) -> str:
    """Fill slot placeholders deterministically; unknown slots raise."""
    dom = rng.choice(_BAD_DOMAINS_PLAIN)
    slots = {
        "ref": ref,
        "amt": rng.choice(_AMOUNTS),
        "otp": rng.choice(_OTPS),
        "vpa": rng.choice(_VPAS),
        "dom": dom,
        "city": rng.choice(_CITIES),
    }
    out = template
    for key, value in slots.items():
        out = out.replace("{" + key + "}", value)
    if "{" in out:
        raise ValueError(f"unfilled slot remains: {out}")
    return out


def _t(text: str, difficulty: str = "easy") -> tuple[str, str]:
    """Template entry: (text with {slots}, difficulty)."""
    return (text, difficulty)


# ---------------------------------------------------------------------------
# Scam strata: every template carries at least one strong-tier pack phrase.
# ---------------------------------------------------------------------------

_TEMPLATES: dict[str, tuple[list[tuple[str, str]], list[tuple[str, str]]]] = {
    "kyc_scam": (
        [
            _t(
                "Dear customer your KYC has expired. Verify now at https://{dom} or your account will be blocked today. Ref {ref}"
            ),
            _t(
                "RBI circular: complete your KYC immediately http://{dom}/kyc{ref} else account frozen",
                "medium",
            ),
            _t(
                "HDFC alert: re-kyc required today. Click www.{dom} and login to update your kyc. Ref {ref}",
                "medium",
            ),
            _t(
                "Your account will be blocked within 24 hours. Update your kyc at {dom} now, ticket {ref}",
                "medium",
            ),
            _t(
                "ICICI: KYC expires today, verify your account immediately via {dom} ref {ref} or card stopped",
                "hard",
            ),
        ],
        [
            _t(
                "आपका केवाईसी समाप्त हो गया है। आज ही https://{dom} पर सत्यापित करें अन्यथा खाता बंद हो जाएगा। संदर्भ {ref}"
            ),
            _t("खाता बंद हो जाएगा, तुरंत सत्यापित करें http://{dom}/r{ref} पर क्लिक करें", "medium"),
            _t("आपका केवाईसी समाप्त, आज {dom} पर अपडेट करें अन्यथा खाता बंद हो जाएगा। रेफ {ref}", "hard"),
        ],
    ),
    "digital_arrest": (
        [
            _t(
                "This is CBI officer Sharma. You are under digital arrest. Stay on video call and transfer Rs {amt} for verification. Case {ref}",
                "medium",
            ),
            _t(
                "TRAI notice {ref}: illegal activities linked to your Aadhaar. Pay penalty Rs {amt} now via UPI to avoid arrest",
                "medium",
            ),
            _t(
                "Mumbai cyber police: your PAN is involved in money laundering. Deposit immediately Rs {amt}. FIR {ref}"
            ),
            _t(
                "Customs officer speaking. Parcel with passports seized at {city}. Stay on video call until verification ends. Ref {ref}",
                "hard",
            ),
        ],
        [
            _t(
                "यह सीबीआई अधिकारी शर्मा है। आप डिजिटल अरेस्ट में हैं। वीडियो कॉल पर रहें और {amt} रुपये के पैसे भेजें। केस {ref}",
                "medium",
            ),
            _t("आपके आधार से अवैध गतिविधि। गिरफ्तारी से बचने के लिए जुर्माना भरें। नोटिस {ref}", "medium"),
            _t("साइबर पुलिस: आपका पैन मनी लॉन्ड्रिंग में है। तुरंत प्रोसेसिंग फीस {amt} भेजें। रेफ {ref}", "medium"),
        ],
    ),
    "investment": (
        [
            _t(
                "Join our trading group! Guaranteed returns 300 percent monthly, limited slots. Register {ref}"
            ),
            _t("Stock tips from ex-Zerodha manager {ref}. Guaranteed profit, pay joining fee now"),
            _t(
                "Crypto arbitrage investment opportunity {ref}, guaranteed returns, only 5 slots left today",
                "medium",
            ),
            _t(
                "Sebi-registered advisor badge {ref}: guaranteed profit daily. Pay joining fee and start earning",
                "hard",
            ),
        ],
        [
            _t("हमारे ट्रेडिंग ग्रुप से जुड़ें! गारंटीड रिटर्न, सीमित स्लॉट। रजिस्टर {ref}", "medium"),
            _t("पूर्व मैनेजर से स्टॉक टिप्स {ref}, गारंटीड रिटर्न, ज्वाइनिंग फीस भेजें", "medium"),
            _t("क्रिप्टो अवसर {ref}, गारंटीड रिटर्न, आज के लिए केवल 5 सीमित स्लॉट", "hard"),
        ],
    ),
    "lottery": (
        [
            _t(
                "Congratulations! You have won Rs {amt} in KBC lottery winner draw {ref}. Claim your prize on WhatsApp"
            ),
            _t(
                "Lucky draw winner {ref}! Your mobile number won the Jio lucky draw. Send processing fee to claim",
                "medium",
            ),
            _t(
                "You have won a car in our annual draw {ref}. Claim your prize within 24 hours by paying tax first",
                "medium",
            ),
        ],
        [
            _t("बधाई हो! आपने केबीसी लॉटरी जीती है {ref}। इनाम का दावा करें"),
            _t("लकी ड्रा विजेता {ref}! आपका नंबर जीता है, प्रोसेसिंग फीस भेजें", "medium"),
            _t("आपने कार जीती है {ref}, 24 घंटे में कर जमा कर दावा करें", "medium"),
        ],
    ),
    "upi_collect_fraud": (
        [
            _t(
                "You received a payment request of Rs {amt}. Enter your UPI PIN to receive money. Txn {ref}",
                "medium",
            ),
            _t(
                "Buyer wants to pay for your OLX item. Scan to receive payment via QR {ref}, do not skip",
                "medium",
            ),
            _t(
                "I accidentally transferred Rs {amt} to your number. Please return it to {vpa} urgently. Ref {ref}",
                "medium",
            ),
            _t(
                "Your account is on hold due to KYC {ref}. Send money to receive your pending refund back",
                "hard",
            ),
            _t(
                "Sent money by mistake to your account {ref}, refund to {vpa} else police complaint",
                "hard",
            ),
        ],
        [
            _t("आपको {amt} रुपये मिलने हैं {ref}, UPI PIN डालकर प्रोसेसिंग फीस जमा करें और पैसे भेजें", "hard"),
            _t("गलती से {amt} रुपये आपके खाते में चले गए {ref}, पैसे वापस भेजें {vpa} पर", "medium"),
            _t("आपका रिफंड {amt} रोक दिया गया है {ref}, पैसे भेजें तभी रिफंड मिलेगा", "hard"),
        ],
    ),
    "courier_scam": (
        [
            _t(
                "FedEx: parcel held at customs {city}. Pay customs clearance of Rs {amt} at {dom} to release your parcel. Ref {ref}"
            ),
            _t(
                "DHL shipment {ref} stuck: release your parcel by paying clearance fee via UPI today",
                "medium",
            ),
            _t(
                "Your package from abroad is detained. Customs clearance required, click www.{dom} booking {ref}",
                "medium",
            ),
        ],
        [
            _t("आपका पार्सल जब्त {city} में हुआ है {ref}, कस्टम शुल्क {amt} भरें और पार्सल छुड़वाएं", "hard"),
            _t("पार्सल जब्त {ref}, जुर्माना भरें आज शाम तक अन्यथा रद्द", "medium"),
        ],
    ),
    "job_task_scam": (
        [
            _t(
                "Part time job guaranteed income {ref}: complete prepaid task orders, earn daily. Pay registration today",
                "medium",
            ),
            _t(
                "Shopping task offer {ref}: commission for completing 3 orders. Prepaid task, payout after deposit",
                "medium",
            ),
            _t(
                "Telegram recruitment {ref}: prepaid task reviews, guaranteed profit, pay joining fee",
                "hard",
            ),
        ],
        [
            _t("हिस्से की नौकरी {ref}, गारंटीड रिटर्न रोज, ज्वाइनिंग फीस भेजें", "hard"),
            _t("घर बैठे काम {ref}, प्रोसेसिंग फीस जमा करें, कमीशन तुरंत", "medium"),
        ],
    ),
    "relative_impersonation": (
        [
            _t(
                "Papa need money urgently {ref}, my phone is broken, this is my new number, send money to {vpa} right away",
                "medium",
            ),
            _t(
                "Mummy need money for hospital deposit {ref}, do not call now, transfer {amt} immediately",
                "medium",
            ),
            _t(
                "Beta papa ko paise bhejo {ref}, main phas gaya hoon, baad me samjhaunga, abhi son send money karo",
                "hard",
            ),
            _t(
                "It is me, daughter send money fast {ref}, I lost my wallet, need {amt} tonight",
                "medium",
            ),
        ],
        [
            _t("पापा को पैसे भेजो {ref}, मेरा फोन खराब है, यह मेरा नया नंबर है, तुरंत भेजो", "medium"),
            _t("मम्मी को पैसे भेजो {ref}, हॉस्पिटल के लिए, अभी कॉल मत करना", "medium"),
            _t("बेटा पैसे भेजो {ref}, मैं फंस गया हूं, बाद में समझाऊंगा", "medium"),
        ],
    ),
    # --- benign: zero strong/moderate phrases; hard tier adds link pressure ---
    "legit_bank_offer": (
        [
            _t(
                "SBI: Get 2x reward points on all online spends till 30 Sep. T&C apply, offer {ref}. Login to onlinesbi.sbi"
            ),
            _t(
                "ICICI Bank: Your credit card bill of Rs {amt} is due on 05-Oct. Pay via icicibank.com, stmt {ref}",
                "medium",
            ),
            _t("Axis Bank: New FD rates up to 7.2 percent p.a. Visit axisbank.com, adv {ref}"),
            _t("HDFC Bank pre-approved personal loan offer {ref}. SMS STOP to opt out", "hard"),
        ],
        [_t("एसबीआई: सभी ऑनलाइन खर्च पर डबल रिवॉर्ड पॉइंट, ऑफर {ref}, शर्तें लागू")],
    ),
    "delivery_update": (
        [
            _t(
                "Your Amazon order {ref} has shipped and will arrive Thursday. Track: amazon.in/track"
            ),
            _t("Zomato: Your order {ref} is out for delivery. Arriving in 12 minutes"),
            _t(
                "BlueDart: Shipment {ref} scheduled for delivery tomorrow 10am-1pm. Track at bluedart.com",
                "medium",
            ),
            _t(
                "Delhivery: package {ref} reached the {city} hub, delivery expected in 2 days. Details: delhivery.com",
                "medium",
            ),
        ],
        [_t("आपका ऑर्डर {ref} कल पहुंच जाएगा, कृपया घर पर रहें")],
    ),
    "govt_notice_legit": (
        [
            _t(
                "IT Department: ITR-1 for AY 2025-26 processed {ref}. Refund of Rs {amt} approved to account ending 4412. Details at incometax.gov.in",
                "medium",
            ),
            _t(
                "EPFO: Your UAN {ref} has been activated. Download your passbook from epfindia.gov.in",
                "medium",
            ),
            _t(
                "Passport update {ref}: application moved to police verification stage at {city}. Track at passportindia.gov.in",
                "hard",
            ),
        ],
        [_t("आयकर विभाग: रिफंड {amt} स्वीकृत {ref}, विवरण incometax.gov.in पर", "medium")],
    ),
    "family_chatter": (
        [
            _t("Mummy calling after lunch, call back when free (fwd {ref})"),
            _t("Did you reach home safe? Message when you do (fwd {ref})"),
            _t("Sunday dinner at 8? Everyone confirmed except you (fwd {ref})"),
            _t(
                "Papa's phone got lost yesterday, he is getting a new SIM today (fwd {ref})", "hard"
            ),
        ],
        [
            _t("खाना तैयार है, जल्दी आ जाओ (फॉरवर्ड {ref})"),
            _t("पापा का फोन कल खो गया था, आज नया सिम ले रहे हैं (फॉरवर्ड {ref})", "hard"),
        ],
    ),
    "newsletter_promo": (
        [
            _t("Your weekly digest {ref}: 10 new articles on personal finance curated for you"),
            _t("Myntra sale alert {ref}: flat 40 percent off on selected styles ends Sunday"),
            _t("Webinar tomorrow {ref}: introduction to mutual funds, register free", "medium"),
            _t("Newsletter {ref}: this week in tech, 5 stories worth reading", "medium"),
        ],
        [_t("साप्ताहिक ऑफर {ref}: चुने हुए सामान पर 40 प्रतिशत छूट, रविवार तक ({ref})")],
    ),
    "otp_forward": (
        [
            _t(
                "Forwarding my OTP because network issue: {otp} is your SBI OTP {ref}, use it quickly",
                "hard",
            ),
            _t("Bhai OTP aa gaya {ref}: {otp} HDFC ka, mera phone switch ho gaya", "hard"),
            _t("Here is the OTP you needed from my number {ref}: {otp} valid 10 min", "hard"),
        ],
        [_t("भाई OTP आ गया {ref}: {otp}, मेरा फोन बंद हो गया ({ref})", "hard")],
    ),
    "govt_legit_trap": (
        [
            _t(
                "IT Department: Your ITR-1 for AY 2025-26 has been processed. Refund of Rs {amt} "
                "approved to your bank account ending 4412. Details at incometax.gov.in, ack {ref}"
            ),
            _t(
                "Income Tax Refund intimation {ref}: refund of Rs {amt} for AY 2025-26 credited "
                "to your account. This is a system-generated message. Check incometax.gov.in"
            ),
        ],
        [
            _t(
                "आयकर विभाग: आपका ITR संसाधित हो गया है। रिफंड {amt} रुपये आपके खाते में "
                "स्वीकृत किया गया है। विवरण incometax.gov.in पर, पावती {ref}",
                "medium",
            ),
            _t(
                "कर अधिसूचना {ref}: AY 2025-26 का रिफंड {amt} रुपये आपके खाते में जमा किया "
                "गया है। यह स्वतः उत्पन्न संदेश है। incometax.gov.in देखें",
                "hard",
            ),
        ],
    ),
}

_PAYMENT_SHARE: dict[str, float] = {
    "kyc_scam": 0.0,
    "digital_arrest": 0.25,
    "investment": 0.5,
    "upi_collect_fraud": 1.0,
    "lottery": 0.3,
    "courier_scam": 0.6,
    "job_task_scam": 0.7,
    "relative_impersonation": 1.0,
}


def _generate_split(seed: int, holdout: bool) -> list[EvalCase]:
    """Draw each stratum's quota, alternating language and cycling templates."""
    counts = _split_counts(FULL_COUNTS, holdout)
    rng = random.Random(seed)
    prefix = "hold" if holdout else "dev"
    lo, hi = (50000, 99999) if holdout else (10000, 49999)
    cases: list[EvalCase] = []
    for stratum, quota in counts.items():  # dict order == STRATA_ORDER insertion
        en_pool, hi_pool = _TEMPLATES[stratum]
        truth = (
            "benign"
            if stratum
            in (
                "legit_bank_offer",
                "delivery_update",
                "govt_notice_legit",
                "family_chatter",
                "newsletter_promo",
                "otp_forward",
                "govt_legit_trap",
            )
            else "scam"
        )
        pay_share = _PAYMENT_SHARE.get(stratum, 0.0)
        for i in range(quota):
            use_hi = i % 2 == 1 and hi_pool
            pool = hi_pool if use_hi else en_pool
            lang = "hi" if use_hi else "en"
            text, difficulty = pool[(i // 2) % len(pool)]
            ref = str(lo + rng.randrange(hi - lo + 1))
            filled = _fill(text, rng, ref)
            cases.append(
                EvalCase(
                    id=f"{prefix}-{stratum}-{i:03d}",
                    stratum=stratum,
                    lang=lang,
                    difficulty=difficulty,
                    ground_truth=truth,
                    text=filled,
                    expect_payment_intent=rng.random() < pay_share,
                )
            )
    expected = HOLDOUT_SET_SIZE if holdout else DEV_SET_SIZE
    assert len(cases) == expected, f"generator drift: {len(cases)} != {expected}"
    return cases


def generate_dev_set(seed: int = DEV_SEED) -> list[EvalCase]:
    """The 480-case dev/calibration set. Safe to inspect and tune against."""
    return _generate_split(seed, holdout=False)


def generate_holdout_set(seed: int = HOLDOUT_SEED) -> list[EvalCase]:
    """The 120-case sealed hold-out. Open exactly twice before submission."""
    return _generate_split(seed, holdout=True)


def check_no_overlap(dev: list[EvalCase], holdout: list[EvalCase]) -> None:
    """Assert dev and hold-out share zero texts.

    Belt-and-braces: the disjoint reference-token ranges make overlap
    structurally impossible, but the assertion costs nothing and fails loud
    if template plumbing ever changes.
    """
    dev_texts = {c.text for c in dev}
    overlap = [c.id for c in holdout if c.text in dev_texts]
    if overlap:
        raise ValueError(f"dev/hold-out overlap detected: {overlap}")


def ensure_split_integrity() -> tuple[list[EvalCase], list[EvalCase]]:
    """Generate both splits fresh and verify the overlap-free contract."""
    dev = generate_dev_set()
    holdout = generate_holdout_set()
    check_no_overlap(dev, holdout)
    return dev, holdout
