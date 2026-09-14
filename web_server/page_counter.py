import os

def get_pdf_info(file_path: str, password: str = None) -> dict:
    """
    Inspects PDF for page count & encryption status.
    Returns dict:
    {
        "page_count": int,
        "is_encrypted": bool,
        "unlocked": bool,
        "error": str or None
    }
    """
    if not os.path.exists(file_path):
        return {"page_count": 1, "is_encrypted": False, "unlocked": True, "error": None}

    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(file_path)
            if reader.is_encrypted:
                if password:
                    try:
                        res = reader.decrypt(password)
                        if res == 0 or res is False:
                            return {"page_count": 0, "is_encrypted": True, "unlocked": False, "error": "Incorrect password"}
                        return {"page_count": len(reader.pages), "is_encrypted": True, "unlocked": True, "error": None}
                    except Exception as dec_err:
                        return {"page_count": 0, "is_encrypted": True, "unlocked": False, "error": str(dec_err)}
                else:
                    return {"page_count": 0, "is_encrypted": True, "unlocked": False, "error": "Password required"}
            else:
                return {"page_count": len(reader.pages), "is_encrypted": False, "unlocked": True, "error": None}
        except Exception as e:
            print(f"[PageCounter Warning] pypdf failed: {e}")
            return {"page_count": 1, "is_encrypted": False, "unlocked": True, "error": None}
    elif ext in [".png", ".jpg", ".jpeg", ".bmp", ".webp"]:
        return {"page_count": 1, "is_encrypted": False, "unlocked": True, "error": None}
    
    return {"page_count": 1, "is_encrypted": False, "unlocked": True, "error": None}

def get_page_count(file_path: str) -> int:
    info = get_pdf_info(file_path)
    return info["page_count"] or 1
