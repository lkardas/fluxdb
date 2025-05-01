class FluxDBError(Exception):
    """Base exception for FluxDB errors."""
    pass

class CollectionNotFoundError(FluxDBError):
    """Raised when a collection does not exist."""
    pass

class TransactionError(FluxDBError):
    """Raised when a transaction operation fails."""
    pass

class RecordEncodingError(FluxDBError):
    """Raised when encoding or decoding a record fails."""
    pass
