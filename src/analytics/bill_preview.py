from src.database.data_connection import get_bill_preview_waste_extra_percent


def get_preview_user_waste_cents(user_row, total_waste_cents, user_count):
    stored = int(user_row.get("waste_cents", -1))
    if stored >= 0:
        base_waste = stored
    elif user_count == 0:
        base_waste = 0
    else:
        base_waste = total_waste_cents / user_count

    extra_percent = get_bill_preview_waste_extra_percent()
    return base_waste * (1 + extra_percent / 100)
