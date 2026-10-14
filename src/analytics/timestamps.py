from datetime import datetime

import pandas as pd


def parse_transaction_timestamps(values):
    parsed = []
    failures = []
    for value in values:
        timestamp = parse_timestamp(value)
        if timestamp is None:
            failures.append(value)
        else:
            parsed.append(timestamp)
    return parsed, failures


def parse_timestamp(value):
    if value is None or str(value).strip() == "":
        return None

    text = str(value).strip()
    for fmt in ("%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass

    try:
        parsed = pd.to_datetime(text, dayfirst=True, errors="coerce")
    except Exception:
        return None
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime().replace(tzinfo=None)
