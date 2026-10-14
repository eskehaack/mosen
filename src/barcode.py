from enum import Enum


class BarcodePartition(Enum):
    def __new__(cls, label: str, minimum: int, maximum: int):
        obj = object.__new__(cls)
        obj._value_ = label
        obj.label = label
        obj.minimum = minimum
        obj.maximum = maximum
        return obj

    DELETE_BASKET = ("delete_basket", 0, 0)
    MULTIPLIER = ("multiplier", 1, 99)
    PRODUCT = ("product", 100, 999)
    USER = ("user", 1000, 99999999999)


def get_barcode(barcode, partition: BarcodePartition) -> int:
    """Parse a barcode and validate that it falls inside a named partition."""
    if barcode is None or barcode == "":
        raise ValueError(f"Empty barcode for partition {partition.label}")

    if isinstance(barcode, bool) or not str(barcode).isdigit():
        raise ValueError(f"Barcode {barcode!r} is not numeric")

    value = int(barcode)
    if not partition.minimum <= value <= partition.maximum:
        raise ValueError(
            f"Barcode {value} is outside partition {partition.label} "
            f"[{partition.minimum}, {partition.maximum}]"
        )

    return value


def is_barcode(barcode, partition: BarcodePartition) -> bool:
    """Return True when barcode can be parsed for the given partition."""
    try:
        get_barcode(barcode, partition)
    except ValueError:
        return False
    return True
