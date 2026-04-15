import datetime as dt
import uuid


def create_timestamp() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def create_uuid() -> str:
    return str(uuid.uuid4())