"""Seed keyword themes and rough CPC bands per estate-planning practice area.

These aren't fed to Claude verbatim as the final keyword list — they ground
the AI generation prompt so it stays on-topic, and the CPC bands drive the
mock traffic simulator so demo performance data looks like real legal-vertical
PPC (estate planning consistently runs $20-90+ CPC on Google Ads).
"""

from app.models import PracticeArea

PRACTICE_AREA_THEMES: dict[PracticeArea, dict] = {
    PracticeArea.WILLS_TRUSTS: {
        "label": "Wills & Trusts",
        "seed_terms": [
            "estate planning attorney", "living trust lawyer", "will and trust attorney",
            "revocable living trust", "last will and testament lawyer", "trust attorney near me",
        ],
        "cpc_range": (25, 65),
    },
    PracticeArea.PROBATE: {
        "label": "Probate",
        "seed_terms": [
            "probate attorney", "probate lawyer near me", "probate litigation attorney",
            "contested probate lawyer", "executor attorney", "probate court lawyer",
        ],
        "cpc_range": (35, 90),
    },
    PracticeArea.ELDER_LAW: {
        "label": "Elder Law",
        "seed_terms": [
            "elder law attorney", "elder law lawyer near me", "nursing home planning attorney",
            "long term care planning lawyer",
        ],
        "cpc_range": (25, 60),
    },
    PracticeArea.POWER_OF_ATTORNEY: {
        "label": "Power of Attorney",
        "seed_terms": [
            "power of attorney lawyer", "durable power of attorney attorney",
            "healthcare power of attorney lawyer",
        ],
        "cpc_range": (18, 45),
    },
    PracticeArea.ASSET_PROTECTION: {
        "label": "Asset Protection",
        "seed_terms": [
            "asset protection attorney", "asset protection trust lawyer",
            "irrevocable trust attorney",
        ],
        "cpc_range": (30, 80),
    },
    PracticeArea.GUARDIANSHIP: {
        "label": "Guardianship",
        "seed_terms": [
            "guardianship attorney", "adult guardianship lawyer", "conservatorship attorney",
        ],
        "cpc_range": (25, 55),
    },
    PracticeArea.SPECIAL_NEEDS_PLANNING: {
        "label": "Special Needs Planning",
        "seed_terms": [
            "special needs trust attorney", "special needs planning lawyer",
        ],
        "cpc_range": (25, 55),
    },
    PracticeArea.MEDICAID_PLANNING: {
        "label": "Medicaid Planning",
        "seed_terms": [
            "medicaid planning attorney", "medicaid asset protection lawyer",
            "medicaid trust attorney",
        ],
        "cpc_range": (28, 65),
    },
}
