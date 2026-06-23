from hidamari.core.text_utils import clean_text


def is_admin_identity(role="", user=""):
    role = clean_text(role)
    user = clean_text(user)
    return role == "admin" or user == "kanri"
