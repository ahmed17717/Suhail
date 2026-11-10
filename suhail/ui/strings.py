"""All user-facing (Arabic) text in one place — easy to review, proofread, or translate."""

# --- chat ---------------------------------------------------------------------
TAB_CHAT = "\U0001f4ac المحادثة"
TAB_ADMIN = "\u2699\ufe0f لوحة التحكم"
CHAT_PLACEHOLDER = "اكتب سؤالك هنا"
CHAT_SPINNER = "جاري البحث والإجابة..."
CHAT_CLEAR = "\U0001f5d1\ufe0f مسح المحادثة"
CHAT_ERROR = "حدث خطأ أثناء معالجة سؤالك. حاول مرة أخرى، وإن استمرت المشكلة فتواصل مع المسؤول."
SOURCES_LABEL = "المصادر"
PAGE_LABEL = "صفحة"

# --- startup ------------------------------------------------------------------
STARTUP_ERROR = "تعذّر تشغيل النظام"

# --- admin: auth --------------------------------------------------------------
ADMIN_LOGIN_TITLE = "دخول المسؤول"
ADMIN_PASSWORD = "كلمة المرور"
ADMIN_LOGIN_BUTTON = "دخول"
ADMIN_LOGOUT = "تسجيل الخروج"
ADMIN_WRONG_PASSWORD = "كلمة المرور غير صحيحة"
ADMIN_DISABLED = "لوحة التحكم معطّلة: لم يتم ضبط كلمة مرور المسؤول (ADMIN_PASSWORD_HASH)."
ADMIN_SESSION_EXPIRED = "انتهت جلسة المسؤول، يرجى تسجيل الدخول مجدداً."


def admin_locked(seconds: int) -> str:
    return f"تم تجاوز عدد المحاولات المسموح بها. حاول مجدداً بعد {seconds} ثانية."


# --- admin: data management ---------------------------------------------------
ADMIN_TITLE = "إدارة البيانات"
UPLOAD_TITLE = "رفع ملف (PDF أو Word أو نص)"
UPLOAD_CHOOSE = "اختر ملف"
UPLOAD_BUTTON = "معالجة ورفع الملف"
UPLOAD_SPINNER = "جاري معالجة الملف..."
REPLACE_YES = "نعم، استبدال الملف الحالي"
CANCEL = "إلغاء"
REPLACED_OK = "تم استبدال الملف بنجاح"
MANUAL_TITLE = "إضافة نص يدوي"
MANUAL_NAME = "عنوان النص"
MANUAL_BODY = "النص"
MANUAL_SAVE = "حفظ النص"
MANUAL_SAVED = "تم حفظ النص"
DOCS_TITLE = "المستندات الحالية"
DOCS_EMPTY = "لا توجد مستندات بعد"
TYPE_MANUAL = "نص يدوي"
TYPE_FILE = "ملف"
EDIT = "تعديل"
EDIT_TEXT = "تعديل النص"
EDIT_SAVE = "حفظ التعديل"
EDIT_SAVED = "تم تحديث النص"
DELETE = "حذف"
DELETE_CONFIRM_YES = "نعم، احذف"
UNEXPECTED_ERROR = "حدث خطأ غير متوقع. راجع سجلات الخادم."


def uploaded_ok(name: str, chunks: int) -> str:
    return f"تم رفع ومعالجة الملف: {name} ({chunks} جزء)"


def duplicate_warning(name: str) -> str:
    return f"يوجد ملف بنفس الاسم '{name}' بالفعل. هل تريد استبداله؟"


def delete_confirm(name: str) -> str:
    return f"هل أنت متأكد من حذف '{name}'؟"


def chunks_label(n: int) -> str:
    return f"{n} جزء"


# --- ingestion error messages (keyed by exception class name) ------------------
def ingestion_error_message(error_type: str, max_mb: int) -> str:
    return {
        "UnsupportedFileTypeError": "نوع الملف غير مدعوم. الأنواع المسموحة: PDF وWord ونص.",
        "FileTooLargeError": f"حجم الملف يتجاوز الحد المسموح ({max_mb} ميجابايت).",
        "EmptyDocumentError": "لم يُعثر على نص قابل للاستخراج (قد يكون الملف ممسوحاً ضوئياً).",
        "ExtractionError": "تعذّرت قراءة الملف؛ قد يكون تالفاً.",
    }.get(error_type, "تعذّرت معالجة الملف.")
