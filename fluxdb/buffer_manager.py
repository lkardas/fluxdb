from typing import Dict, List, Optional
from .exceptions import FluxDBError
from .storage import StorageBackend

class BufferManager:
    """Manages in-memory buffering of records before writing to disk."""
    
    def __init__(self, db_path: str, storage: StorageBackend, buffer_size: int):
        self.db_path = db_path
        self.storage = storage
        self.buffer_size = buffer_size
        self.buffer: Dict[str, List[bytes]] = {}

    def append_to_buffer(self, collection: str, record_bytes: bytes) -> None:
        """
        Appends a record to the buffer.

        Args:
            collection (str): Name of the collection.
            record_bytes (bytes): Encoded record data.
        """
        if collection not in self.buffer:
            self.buffer[collection] = []
        self.buffer[collection].append(record_bytes)

    def is_buffer_full(self, collection: str) -> bool:
        """
        Checks if the buffer for a collection is full.

        Args:
            collection (str): Name of the collection.

        Returns:
            bool: True if the buffer is full, False otherwise.
        """
        return collection in self.buffer and len(self.buffer[collection]) >= self.buffer_size

    def flush_buffer(self, collection: Optional[str] = None) -> None:
        """
        Flushes the in-memory buffer to disk.

        Args:
            collection (Optional[str]): Specific collection to flush, or None for all.

        Raises:
            FluxDBError: If file operation fails.
        """
        collections = [collection] if collection else list(self.buffer.keys())
        for col in collections:
            if col in self.buffer and self.buffer[col]:
                try:
                    collection_path = os.path.join(self.db_path, f"{col}.fdb")
                    with open(collection_path, 'ab') as f:
                        for record in self.buffer[col]:
                            f.write(record)
                    self.buffer[col] = []
                except IOError as e:
                    raise FluxDBError(f"Failed to flush buffer for {col}: {e}")
