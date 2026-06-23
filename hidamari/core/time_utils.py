from datetime import datetime, timedelta

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None


JST = ZoneInfo("Asia/Tokyo") if ZoneInfo else None


def now_jst_dt():
    if JST:
        return datetime.now(JST)
    return datetime.utcnow() + timedelta(hours=9)


def format_now_jst(fmt="%Y-%m-%d %H:%M:%S"):
    return now_jst_dt().strftime(fmt)


def now_jst():
    return format_now_jst("%Y-%m-%d %H:%M:%S")


def today_jst():
    return now_jst_dt().date()
