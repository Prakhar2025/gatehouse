"""Seeded mini-set generator: 30 cases across the doc-07 strata.

Deterministic under a fixed seed: same seed, byte-identical set. This is the
P1 offline benchmark; P2/P6 scale it to 480/600 via the same code path.
"""

from __future__ import annotations

import random

from gatehouse.evaluation.schemas import EvalCase

_SEED = 42
_CASES_PER_STRATUM_PAIR = 3  # per language inside each stratum

# Total cases the mini set produces; asserted by tests and docs.
MINI_SET_SIZE = 37  # 12 en templates + 12 hi templates + 12 benign en + 1 hard trap

# (stratum, ground_truth, difficulty, templates_en, templates_hi)
_BLUEPRINTS: list[tuple[str, str, str, list[str], list[str]]] = [
    (
        "kyc_scam",
        "scam",
        "easy",
        [
            "Dear customer your KYC has expired. Verify now at https://sbi-kyc-update[.]top or account will be blocked today",
            "RBI circular: complete your KYC immediately http://rbi-notice[.]site/kyc else account frozen",
            "HDFC alert: re-kyc required today. Click www.hdfc-verify[.]xyz and login",
        ],
        [
            "आपका केवाईसी समाप्त हो गया है। आज ही सत्यापित करें https://sbi-kyc[.]top अन्यथा खाता बंद हो जाएगा",
            "तत्काल केवाईसी अपडेट करें http://rbi-kyc[.]site पर क्लिक करें",
            "खाता ब्लॉक होने से बचने के लिए तुरंत सत्यापित करें",
        ],
    ),
    (
        "digital_arrest",
        "scam",
        "medium",
        [
            "This is CBI officer Sharma. You are under digital arrest. Stay on video call and transfer funds for verification",
            "TRAI notice: illegal activities linked to your Aadhaar. Pay penalty via UPI to avoid arrest",
            "Mumbai cyber police: your PAN is involved in money laundering. Deposit processing fee immediately",
        ],
        [
            "यह सीबीआई अधिकारी शर्मा है। आप डिजिटल अरेस्ट में हैं। वीडियो कॉल पर रहें और पैसे ट्रांसफर करें",
            "आपके आधार से अवैध गतिविधि। गिरफ्तारी से बचने के लिए जुर्माना भरें",
            "साइबर पुलिस: आपका पैन मनी लॉन्ड्रिंग में है। तुरंत प्रोसेसिंग फीस भेजें",
        ],
    ),
    (
        "investment",
        "scam",
        "medium",
        [
            "Join our trading group! Guaranteed returns 300% monthly, limited slots. DM for link",
            "Stock tips from ex-Zerodha manager. Guaranteed profit, pay joining fee now",
            "Crypto arbitrage opportunity, guaranteed returns, only 5 slots left today",
        ],
        [
            "हमारे ट्रेडिंग ग्रुप से जुड़ें! गारंटीड रिटर्न, सीमित स्लॉट",
            "पूर्व मैनेजर से स्टॉक टिप्स, गारंटीड प्रॉफिट, ज्वाइनिंग फीस भेजें",
            "क्रिप्टो अवसर, गारंटीड रिटर्न, आज के लिए केवल 5 स्लॉट",
        ],
    ),
    (
        "lottery",
        "scam",
        "easy",
        [
            "Congratulations! You have won Rs 25,00,000 in KBC lottery. Claim your prize: WhatsApp your details",
            "Lucky draw winner! Your mobile number won the Jio lottery. Send processing fee to claim",
            "You have won a car in our annual draw. Claim within 24 hours by paying tax first",
        ],
        [
            "बधाई हो! आपने केबीसी लॉटरी जीती है। इनाम का दावा करें",
            "लकी ड्रा विजेता! आपका नंबर जीता है, प्रोसेसिंग फीस भेजें",
            "आपने कार जीती है, 24 घंटे में कर जमा कर दावा करें",
        ],
    ),
    (
        "legit_bank_offer",
        "benign",
        "medium",
        [
            "SBI: Get 2x reward points on all online spends till 30 Sep. T&C apply. Login to onlinesbi.sbi",
            "ICICI Bank: Your credit card bill of Rs 2,450 is due on 05-Oct. Pay via icicibank.com",
            "Axis Bank: New FD rates up to 7.2% p.a. Visit axisbank.com to know more",
        ],
        [],
    ),
    (
        "delivery_update",
        "benign",
        "easy",
        [
            "Your Amazon order has shipped and will arrive Thursday. Track: amazon.in/track",
            "Zomato: Your order is out for delivery. Arriving in 12 minutes",
            "BlueDart: Shipment 482910 scheduled for delivery tomorrow between 10am-1pm",
        ],
        [],
    ),
    (
        "family_chatter",
        "benign",
        "easy",
        [
            "Mummy calling after lunch, call back when free",
            "Did you reach home safe? Message when you do",
            "Sunday dinner at 8? Everyone confirmed except you",
        ],
        [],
    ),
    (
        "otp_forward",
        "benign",
        "hard",
        [
            "Forwarding my OTP because network issue: 449210 is your SBI OTP, use it quickly",
            "Bhai OTP aa gaya: 883214 HDFC ka, mera phone switch ho gaya",
            "Here is the OTP you needed from my number: 771063 valid 10 min",
        ],
        [],
    ),
]

_TRAP_NOTE_EN = (
    # hard benign trap: scary-looking but genuine government-style wording
    "IT Department: Your ITR-1 for AY 2025-26 has been processed. Refund of Rs 18,240 "
    "approved to your bank account ending 4412. Details at incometax.gov.in"
)


def generate_mini_set(seed: int = _SEED) -> list[EvalCase]:
    """Build the deterministic mini set; length equals MINI_SET_SIZE."""
    rng = random.Random(seed)
    cases: list[EvalCase] = []
    counter = 0
    for stratum, truth, difficulty, en_templates, hi_templates in _BLUEPRINTS:
        for template in en_templates:
            counter += 1
            cases.append(
                EvalCase(
                    id=f"mini-{counter:03d}",
                    stratum=stratum,
                    lang="en",
                    difficulty=difficulty,
                    ground_truth=truth,
                    text=template,
                    expect_payment_intent=rng.random() > 0.5,
                )
            )
        for template in hi_templates:
            counter += 1
            cases.append(
                EvalCase(
                    id=f"mini-{counter:03d}",
                    stratum=stratum,
                    lang="hi",
                    difficulty=difficulty,
                    ground_truth=truth,
                    text=template,
                    expect_payment_intent=False,
                )
            )
    # One hand-built hard trap so the hardest benign class always exists even
    # if blueprint counts change later.
    counter += 1
    cases.append(
        EvalCase(
            id=f"mini-{counter:03d}",
            stratum="govt_legit_trap",
            lang="en",
            difficulty="hard",
            ground_truth="benign",
            text=_TRAP_NOTE_EN,
        )
    )
    assert len(cases) == MINI_SET_SIZE, f"generator drift: {len(cases)} != {MINI_SET_SIZE}"
    return cases
