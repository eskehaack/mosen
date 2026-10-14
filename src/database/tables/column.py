from src.barcode import BarcodePartition, is_barcode


class Column():
    def __init__(self, name, dtype, required=True, default=None, is_primary_key=False):
        self.name = name
        self.dtype = dtype
        self.required = required
        self.default = default
        self.is_primary_key = is_primary_key

    def __repr__(self):
        return f"Column(name='{self.name}', dtype='{self.dtype}', required={self.required}, default={self.default}, is_primary_key={self.is_primary_key})"
    
class BarcodeColumn(Column):
    def __init__(self, name, dtype, partition: BarcodePartition, required=True, default=None, is_primary_key=False):
        super().__init__(name, dtype, required, default, is_primary_key)
        if partition is None:
            raise ValueError("BarcodeColumn requires a BarcodePartition")
        self.partition = partition

    def is_valid_barcode(self, value):
        """Check if value is a valid barcode using the partition spec."""
        return is_barcode(value, self.partition)
