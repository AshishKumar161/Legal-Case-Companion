import logging
from typing import Any

from fastapi import Request

from app.models.user import User

logger = logging.getLogger(__name__)

SUPPORTED_LOCALES = ("en-IN", "hi-IN")
DEFAULT_LOCALE = "en-IN"

# Built-in fallback dictionary for core system and legal strings
TRANSLATION_CATALOG: dict[str, dict[str, str]] = {
    "en-IN": {
        "common.appName": "Legal Case Companion",
        "common.save": "Save",
        "common.cancel": "Cancel",
        "common.delete": "Delete",
        "common.confirm": "Confirm",
        "auth.login.title": "Sign In to Your Account",
        "auth.register.title": "Create Your Account",
        "auth.email": "Email Address",
        "auth.password": "Password",
        "cases.title": "Legal Matters & Cases",
        "cases.create": "Create New Matter",
        "consultations.title": "Advocate Consultations",
        "consultations.book": "Book Consultation",
        "evidence.title": "Evidence Locker",
        "evidence.upload": "Upload Evidence Exhibit",
        "evidence.quarantined": "Evidence in Quarantine - Scanning for Malware",
        "ai.copilot.title": "Legal AI Research Companion",
        "ai.disclaimer": "AI provides legal information and research assistance only, not guaranteed legal advice. Professional advice requires a verified advocate.",
        "trust.legalTransparency": "Advocate advice is provided solely by Bar Council of India verified advocates. AI assists with statutory research and document analysis.",
        "errors.notFound": "Requested resource was not found.",
        "errors.unauthorized": "Authentication credentials were not provided or have expired.",
        "errors.forbidden": "You do not have permission to access this resource.",
        "errors.emergencyReadOnly": "Platform is temporarily in emergency read-only mode for maintenance.",
    },
    "hi-IN": {
        "common.appName": "लीगल केस कम्पैनियन (Legal Case Companion)",
        "common.save": "सहेजें",
        "common.cancel": "रद्द करें",
        "common.delete": "हटाएं",
        "common.confirm": "पुष्टि करें",
        "auth.login.title": "अपने खाते में साइन इन करें",
        "auth.register.title": "नया खाता बनाएं",
        "auth.email": "ईमेल पता",
        "auth.password": "पासवर्ड",
        "cases.title": "विधिक मामले एवं वाद",
        "cases.create": "नया मामला दर्ज करें",
        "consultations.title": "अधिवक्ता परामर्श",
        "consultations.book": "परामर्श बुक करें",
        "evidence.title": "साक्ष्य लॉकर (Evidence Locker)",
        "evidence.upload": "साक्ष्य दस्तावेज अपलोड करें",
        "evidence.quarantined": "साक्ष्य संगरोध (क्वारंटाइन) में है - मैलवेयर की जांच जारी है",
        "ai.copilot.title": "विधिक एआई अनुसंधान सहायक",
        "ai.disclaimer": "एआई केवल कानूनी जानकारी और अनुसंधान सहायता प्रदान करता है, कोई गारंटीकृत कानूनी सलाह नहीं। पेशेवर सलाह के लिए प्रमाणित अधिवक्ता आवश्यक है।",
        "trust.legalTransparency": "अधिवक्ता सलाह केवल बार काउंसिल ऑफ इंडिया द्वारा सत्यापित अधिवक्ताओं द्वारा दी जाती है। एआई केवल वैधानिक अनुसंधान में सहायता करता है।",
        "errors.notFound": "अनुरोधित संसाधन नहीं मिला।",
        "errors.unauthorized": "प्रमाणीकरण क्रेडेंशियल प्रदान नहीं किए गए हैं या समाप्त हो गए हैं।",
        "errors.forbidden": "आपके पास इस संसाधन तक पहुँचने की अनुमति नहीं है।",
        "errors.emergencyReadOnly": "सुरक्षा और रखरखाव के लिए प्लेटफ़ॉर्म अस्थायी रूप से केवल-पढ़ने के मोड में है।",
    },
}


def resolve_locale(request: Request | None = None, current_user: User | None = None) -> str:
    """Resolves target locale with language-safe fallback hierarchy (Part C).

    Order of precedence:
    1. Authenticated user's account_locale
    2. Query parameter 'locale' (if present and valid)
    3. 'Accept-Language' HTTP header (e.g. 'hi-IN', 'hi', 'en-IN')
    4. DEFAULT_LOCALE ('en-IN')
    """
    if current_user and getattr(current_user, "account_locale", None) in SUPPORTED_LOCALES:
        return current_user.account_locale

    if request:
        # Check query param
        query_loc = request.query_params.get("locale")
        if query_loc in SUPPORTED_LOCALES:
            return query_loc

        # Check Accept-Language
        accept_lang = request.headers.get("accept-language", "")
        for item in accept_lang.split(","):
            candidate = item.split(";")[0].strip()
            if candidate in SUPPORTED_LOCALES:
                return candidate
            if candidate.startswith("hi"):
                return "hi-IN"
            if candidate.startswith("en"):
                return "en-IN"

    return DEFAULT_LOCALE


def translate(key: str, locale: str = DEFAULT_LOCALE, params: dict[str, Any] | None = None) -> str:
    """Retrieves translated text from the catalog with fallback to English."""
    loc_dict = TRANSLATION_CATALOG.get(locale) or TRANSLATION_CATALOG[DEFAULT_LOCALE]
    text = loc_dict.get(key) or TRANSLATION_CATALOG[DEFAULT_LOCALE].get(key, key)

    if params:
        for p_key, p_val in params.items():
            text = text.replace(f"{{{p_key}}}", str(p_val))
    return text
