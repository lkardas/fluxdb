import os
import struct
from typing import Dict, List, Set
from .exceptions import FluxDBError
from .storage import StorageBackend

class RecordLoader:
    """Loads records from collection files."""
    
    def __init__(self, storage: StorageBackend):
        self.storage = storage

    def load_all_records(self, collection_path: str) -> List[Dict]:
        """
        Loads all records from a collection file.

        Args:
            collection_path (str): Path to the collection file.

        Returns:
            List[Dict]: List of decoded records.

        Raises:
            FluxDBError: If file operation or decoding fails.
        """
        records = []
        try:
            with open(collection_path, 'rb') as f:
                file_size = os.path.getsize(collection_path)
                offset = 0
                while offset < file_size:
                    f.seek(offset)
                    len_bytes = f.read(4)
                    if len(len_bytes) < 4:
                        break
                    record_len = struct.unpack('!I', len_bytes)[0]
                    if offset + 4 + record_len > file_size:
                        break
                    record_data = f.read(record_len)
                    if len(record_data) < record_len:
                        break
                    record = self.storage.decode_record(record_data)
                    if record:
                        records.append(record)
                    offset += 4 + record_len
        except (IOError, struct.error) as e:
            raise FluxDBError(f"Failed to load records: {e}")
        return records

    def load_records_by_ids(self, collection_path: str, record_ids: Set[str]) -> List[Dict]:
        """
        Loads records by their IDs.

        Args:
            collection_path (str): Path to the collection file.
            record_ids (Set[str]): Set of record IDs to load.

        Returns:
            List[Dict]: List of matching records.

        Raises:
            FluxDBError: If file operation or decoding fails.
        """
        records = []
        try:
            with open(collection_path, 'rb') as f:
                file_size = os.path.getsize(collection_path)
                offset = 0
                while offset < file_size:
                    f.seek(offset)
                    len_bytes = f.read(4)
                    if len(len_bytes) < 4:
                        break
                    record_len = struct.unpack('!I', len_bytes)[0]
                    if offset + 4 + record_len > file_size:
                        break
                    record_data = f.read(record_len)
                    if len(record_data) < record_len:
                        break
                    record = self.storage.decode_record(record_data)
                    if record and record['_id'] in record_ids:
                        records.append(record)
                    offset += 4 + record_len
        except (IOError, struct.error) as e:
            raise FluxDBError(f"Failed to load records by IDs: {e}")
        return records
