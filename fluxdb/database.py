import os
import uuid
from typing import Dict, List, Set, Optional, Callable
from .indexing import IndexManager
from .storage import BinaryStorage, StorageBackend
from .exceptions import FluxDBError, CollectionNotFoundError, TransactionError

class FluxDB:
    """A lightweight file-based NoSQL database with collections, indexing, and transactions.

    Args:
        db_path (str): Path to the database directory.
        buffer_size (int): Size of the in-memory buffer for write operations.
        storage_backend (StorageBackend): Backend for record encoding/decoding.
    """
    def __init__(self, db_path: str, buffer_size: int = 1000, storage_backend: StorageBackend = None):
        self.db_path = db_path
        self.buffer_size = buffer_size
        self.storage = storage_backend or BinaryStorage()
        self.index_manager = IndexManager(db_path)
        self.buffer: Dict[str, List[bytes]] = {}
        self.transaction_active = False
        self.transaction_buffer: List[Dict] = []
        os.makedirs(db_path, exist_ok=True)

    def _get_collection_path(self, collection: str) -> str:
        """Returns the file path for a collection."""
        return os.path.join(self.db_path, f"{collection}.fdb")

    def create_collection(self, collection: str, indexed_fields: Optional[List[str]] = None) -> bool:
        """Creates a new collection.

        Args:
            collection (str): Name of the collection.
            indexed_fields (Optional[List[str]]): Fields to index.

        Returns:
            bool: True if created, False if already exists.
        """
        collection_path = self._get_collection_path(collection)
        if os.path.exists(collection_path):
            return False
        with open(collection_path, 'wb') as f:
            f.write(b"")
        if indexed_fields:
            self.index_manager.create_index(collection, indexed_fields)
        return True

    def drop_collection(self, collection: str) -> bool:
        """Drops a collection and its indexes.

        Args:
            collection (str): Name of the collection.

        Returns:
            bool: True if dropped, False if not found.
        """
        collection_path = self._get_collection_path(collection)
        if not os.path.exists(collection_path):
            return False
        os.remove(collection_path)
        self.index_manager.drop_index(collection)
        if collection in self.buffer:
            del self.buffer[collection]
        return True

    def clear_collection(self, collection: str) -> bool:
        """Clears a collection, preserving its indexes.

        Args:
            collection (str): Name of the collection.

        Returns:
            bool: True if cleared, False if not found.
        """
        collection_path = self._get_collection_path(collection)
        if not os.path.exists(collection_path):
            return False
        with open(collection_path, 'wb') as f:
            f.write(b"")
        self.index_manager.clear_index(collection)
        if collection in self.buffer:
            self.buffer[collection] = []
        return True

    def begin_transaction(self) -> None:
        """Begins a transaction."""
        if self.transaction_active:
            raise TransactionError("Transaction already active")
        self.transaction_active = True
        self.transaction_buffer = []

    def commit(self) -> None:
        """Commits a transaction."""
        if not self.transaction_active:
            raise TransactionError("No active transaction")
        try:
            for op in self.transaction_buffer:
                op['func'](*op['args'], **op['kwargs'])
            self.transaction_buffer = []
            self.transaction_active = False
            self._flush_buffer()
        except Exception as e:
            raise TransactionError(f"Failed to commit transaction: {e}")

    def rollback(self) -> None:
        """Rolls back a transaction."""
        if not self.transaction_active:
            raise TransactionError("No active transaction")
        self.transaction_buffer = []
        self.transaction_active = False

    def _add_to_transaction(self, func: Callable, *args, **kwargs) -> None:
        """Adds an operation to a transaction or executes it immediately."""
        if self.transaction_active:
            self.transaction_buffer.append({'func': func, 'args': args, 'kwargs': kwargs})
        else:
            func(*args, **kwargs)

    def _flush_buffer(self, collection: Optional[str] = None) -> None:
        """Flushes the in-memory buffer to disk.

        Args:
            collection (Optional[str]): Specific collection to flush, or None for all.
        """
        collections = [collection] if collection else list(self.buffer.keys())
        for col in collections:
            if col in self.buffer and self.buffer[col]:
                try:
                    with open(self._get_collection_path(col), 'ab') as f:
                        for record in self.buffer[col]:
                            f.write(record)
                    self.buffer[col] = []
                except IOError as e:
                    raise FluxDBError(f"Failed to flush buffer for {col}: {e}")

    def insert(self, collection: str, data: Dict) -> str:
        """Inserts a new record.

        Args:
            collection (str): Name of the collection.
            data (Dict): Record to insert.

        Returns:
            str: ID of the inserted record.

        Raises:
            CollectionNotFoundError: If the collection does not exist.
        """
        def _insert():
            record_id = data.get('_id', str(uuid.uuid4()))
            record_bytes = self.storage.encode_record(data)
            if collection not in self.buffer:
                self.buffer[collection] = []
            self.buffer[collection].append(record_bytes)
            self.index_manager.update_index(collection, data)
            if len(self.buffer[collection]) >= self.buffer_size:
                self._flush_buffer(collection)
            return record_id

        collection_path = self._get_collection_path(collection)
        if not os.path.exists(collection_path):
            self.create_collection(collection)
        self._add_to_transaction(_insert)
        return data.get('_id', str(uuid.uuid4()))

    def insert_many(self, collection: str, data_list: List[Dict]) -> List[str]:
        """Inserts multiple records.

        Args:
            collection (str): Name of the collection.
            data_list (List[Dict]): List of records to insert.

        Returns:
            List[str]: IDs of inserted records.
        """
        return [self.insert(collection, data) for data in data_list]

    def find(self, collection: str, query: Optional[Dict] = None, limit: Optional[int] = None,
             skip: int = 0, sort: Optional[Dict] = None) -> List[Dict]:
        """Finds records matching a query.

        Args:
            collection (str): Name of the collection.
            query (Optional[Dict]): Query dictionary.
            limit (Optional[int]): Maximum number of records to return.
            skip (int): Number of records to skip.
            sort (Optional[Dict]): Sort criteria.

        Returns:
            List[Dict]: List of matching records.

        Raises:
            CollectionNotFoundError: If the collection does not exist.
        """
        collection_path = self._get_collection_path(collection)
        if not os.path.exists(collection_path):
            raise CollectionNotFoundError(f"Collection {collection} not found")

        records = []
        if query and self.index_manager.can_use_index(collection, query):
            record_ids = self.index_manager.query_index(collection, query)
            records = self._load_records_by_ids(collection_path, record_ids)
        else:
            records = self._load_all_records(collection_path)

        if query:
            records = self._filter_records(records, query)

        if sort:
            records = self._sort_records(records, sort)

        records = records[skip:]
        if limit is not None:
            records = records[:limit]

        if collection in self.buffer:
            buffered_records = [r for r in (self.storage.decode_record(b) for b in self.buffer[collection]) if r]
            records.extend(self._filter_records(buffered_records, query))
            if sort:
                records = self._sort_records(records, sort)
            records = records[skip:skip+limit if limit else None]

        return records

    def _load_all_records(self, collection_path: str) -> List[Dict]:
        """Loads all records from a collection file.

        Args:
            collection_path (str): Path to the collection file.

        Returns:
            List[Dict]: List of decoded records.
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

    def _load_records_by_ids(self, collection_path: str, record_ids: Set[str]) -> List[Dict]:
        """Loads records by their IDs.

        Args:
            collection_path (str): Path to the collection file.
            record_ids (Set[str]): Set of record IDs to load.

        Returns:
            List[Dict]: List of matching records.
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

    def _filter_records(self, records: List[Dict], query: Dict) -> List[Dict]:
        """Filters records based on a query.

        Args:
            records (List[Dict]): Records to filter.
            query (Dict): Query dictionary.

        Returns:
            List[Dict]: Filtered records.
        """
        results = []
        for record in records:
            matches = True
            for key, condition in query.items():
                if isinstance(condition, dict):
                    for op, value in condition.items():
                        record_value = record.get(key, "")
                        try:
                            record_num = float(record_value) if record_value else 0
                            if op == '$gt' and not (record_num > value):
                                matches = False
                            elif op == '$lt' and not (record_num < value):
                                matches = False
                            elif op == '$in' and record_value not in value:
                                matches = False
                        except ValueError:
                            matches = False
                elif record.get(key) != str(condition):
                    matches = False
            if matches:
                results.append(record)
        return results

    def _sort_records(self, records: List[Dict], sort: Dict) -> List[Dict]:
        """Sorts records based on sort criteria.

        Args:
            records (List[Dict]): Records to sort.
            sort (Dict): Sort criteria.

        Returns:
            List[Dict]: Sorted records.
        """
        def key_func(record):
            keys = []
            for field, direction in sort.items():
                value = record.get(field, "")
                try:
                    value = float(value)
                except ValueError:
                    pass
                keys.append((value, direction))
            return keys

        return sorted(records, key=key_func, reverse=any(v == -1 for v in sort.values()))

    def update(self, collection: str, record_id: str, update_data: Dict) -> bool:
        """Updates a record by ID.

        Args:
            collection (str): Name of the collection.
            record_id (str): ID of the record to update.
            update_data (Dict): Data to update.

        Returns:
            bool: True if updated, False if not found.

        Raises:
            CollectionNotFoundError: If the collection does not exist.
        """
        def _update():
            records = self._load_all_records(collection_path)
            updated = False
            for record in records:
                if record['_id'] == record_id:
                    record.update(update_data)
                    updated = True
                    break
            if updated:
                with open(collection_path, 'wb') as f:
                    for record in records:
                        f.write(self.storage.encode_record(record))
                self.index_manager.update_index(collection, record)
            return updated

        collection_path = self._get_collection_path(collection)
        if not os.path.exists(collection_path):
            raise CollectionNotFoundError(f"Collection {collection} not found")
        self._add_to_transaction(_update)
        return True

    def delete(self, collection: str, record_id: str) -> bool:
        """Deletes a record by ID.

        Args:
            collection (str): Name of the collection.
            record_id (str): ID of the record to delete.

        Returns:
            bool: True if deleted, False if not found.

        Raises:
            CollectionNotFoundError: If the collection does not exist.
        """
        def _delete():
            records = self._load_all_records(collection_path)
            initial_len = len(records)
            records = [r for r in records if r['_id'] != record_id]
            if len(records) < initial_len:
                with open(collection_path, 'wb') as f:
                    for record in records:
                        f.write(self.storage.encode_record(record))
                self.index_manager.remove_from_index(collection, record_id)
                return True
import os
import uuid
import struct
from typing import Dict, List, Set, Optional, Callable
from .indexing import IndexManager
from .storage import BinaryStorage, StorageBackend
from .exceptions import FluxDBError, CollectionNotFoundError, TransactionError

class FluxDB:
    """A lightweight file-based NoSQL database with collections, indexing, and transactions.

    Args:
        db_path (str): Path to the database directory.
        buffer_size (int): Size of the in-memory buffer for write operations.
        storage_backend (StorageBackend): Backend for record encoding/decoding.
    """
    def __init__(self, db_path: str, buffer_size: int = 1000, storage_backend: StorageBackend = None):
        self.db_path = db_path
        self.buffer_size = buffer_size
        self.storage = storage_backend or BinaryStorage()
        self.index_manager = IndexManager(db_path)
        self.buffer: Dict[str, List[bytes]] = {}
        self.transaction_active = False
        self.transaction_buffer: List[Dict] = []
        os.makedirs(db_path, exist_ok=True)
        os.makedirs(os.path.join(db_path, 'indexes'), exist_ok=True)  # Создаём директорию indexes

    def _get_collection_path(self, collection: str) -> str:
        """Returns the file path for a collection."""
        return os.path.join(self.db_path, f"{collection}.fdb")

    def create_collection(self, collection: str, indexed_fields: Optional[List[str]] = None) -> bool:
        """Creates a new collection.

        Args:
            collection (str): Name of the collection.
            indexed_fields (Optional[List[str]]): Fields to index.

        Returns:
            bool: True if created, False if already exists.
        """
        collection_path = self._get_collection_path(collection)
        if os.path.exists(collection_path):
            return False
        with open(collection_path, 'wb') as f:
            f.write(b"")
        if indexed_fields:
            self.index_manager.create_index(collection, indexed_fields)
        return True

    def drop_collection(self, collection: str) -> bool:
        """Drops a collection and its indexes.

        Args:
            collection (str): Name of the collection.

        Returns:
            bool: True if dropped, False if not found.
        """
        collection_path = self._get_collection_path(collection)
        if not os.path.exists(collection_path):
            return False
        os.remove(collection_path)
        self.index_manager.drop_index(collection)
        if collection in self.buffer:
            del self.buffer[collection]
        return True

    def clear_collection(self, collection: str) -> bool:
        """Clears a collection, preserving its indexes.

        Args:
            collection (str): Name of the collection.

        Returns:
            bool: True if cleared, False if not found.
        """
        collection_path = self._get_collection_path(collection)
        if not os.path.exists(collection_path):
            return False
        with open(collection_path, 'wb') as f:
            f.write(b"")
        self.index_manager.clear_index(collection)
        if collection in self.buffer:
            self.buffer[collection] = []
        return True

    def begin_transaction(self) -> None:
        """Begins a transaction."""
        if self.transaction_active:
            raise TransactionError("Transaction already active")
        self.transaction_active = True
        self.transaction_buffer = []

    def commit(self) -> None:
        """Commits a transaction."""
        if not self.transaction_active:
            raise TransactionError("No active transaction")
        try:
            for op in self.transaction_buffer:
                op['func'](*op['args'], **op['kwargs'])
            self.transaction_buffer = []
            self.transaction_active = False
            self._flush_buffer()
        except Exception as e:
            raise TransactionError(f"Failed to commit transaction: {e}")

    def rollback(self) -> None:
        """Rolls back a transaction."""
        if not self.transaction_active:
            raise TransactionError("No active transaction")
        self.transaction_buffer = []
        self.transaction_active = False

    def _add_to_transaction(self, func: Callable, *args, **kwargs) -> None:
        """Adds an operation to a transaction or executes it immediately."""
        if self.transaction_active:
            self.transaction_buffer.append({'func': func, 'args': args, 'kwargs': kwargs})
        else:
            func(*args, **kwargs)

    def _flush_buffer(self, collection: Optional[str] = None) -> None:
        """Flushes the in-memory buffer to disk.

        Args:
            collection (Optional[str]): Specific collection to flush, or None for all.
        """
        collections = [collection] if collection else list(self.buffer.keys())
        for col in collections:
            if col in self.buffer and self.buffer[col]:
                try:
                    collection_path = self._get_collection_path(col)
                    with open(collection_path, 'ab') as f:
                        for record in self.buffer[col]:
                            f.write(record)
                    print(f"Flushed {len(self.buffer[col])} records to {collection_path}")  # Отладка
                    self.buffer[col] = []
                except IOError as e:
                    print(f"Failed to flush buffer for {col}: {e}")  # Отладка
                    raise FluxDBError(f"Failed to flush buffer for {col}: {e}")

    def insert(self, collection: str, data: Dict) -> str:
        """Inserts a new record.

        Args:
            collection (str): Name of the collection.
            data (Dict): Record to insert.

        Returns:
            str: ID of the inserted record.

        Raises:
            CollectionNotFoundError: If the collection does not exist.
        """
        def _insert():
            record_id = data.get('_id', str(uuid.uuid4()))
            data_with_id = data.copy()
            data_with_id['_id'] = record_id
            record_bytes = self.storage.encode_record(data_with_id)
            if collection not in self.buffer:
                self.buffer[collection] = []
            self.buffer[collection].append(record_bytes)
            self.index_manager.update_index(collection, data_with_id)
            print(f"Inserted to buffer: {data_with_id}")  # Отладка
            if len(self.buffer[collection]) >= self.buffer_size:
                self._flush_buffer(collection)
            return record_id

        collection_path = self._get_collection_path(collection)
        if not os.path.exists(collection_path):
            self.create_collection(collection)
        self._add_to_transaction(_insert)
        return data.get('_id', str(uuid.uuid4()))

    def insert_many(self, collection: str, data_list: List[Dict]) -> List[str]:
        """Inserts multiple records.

        Args:
            collection (str): Name of the collection.
            data_list (List[Dict]): List of records to insert.

        Returns:
            List[str]: IDs of inserted records.
        """
        return [self.insert(collection, data) for data in data_list]

    def find(self, collection: str, query: Optional[Dict] = None, limit: Optional[int] = None,
             skip: int = 0, sort: Optional[Dict] = None) -> List[Dict]:
        """Finds records matching a query.

        Args:
            collection (str): Name of the collection.
            query (Optional[Dict]): Query dictionary.
            limit (Optional[int]): Maximum number of records to return.
            skip (int): Number of records to skip.
            sort (Optional[Dict]): Sort criteria.

        Returns:
            List[Dict]: List of matching records.

        Raises:
            CollectionNotFoundError: If the collection does not exist.
        """
        collection_path = self._get_collection_path(collection)
        if not os.path.exists(collection_path):
            raise CollectionNotFoundError(f"Collection {collection} not found")

        records = []
        if query and self.index_manager.can_use_index(collection, query):
            record_ids = self.index_manager.query_index(collection, query)
            print(f"Index query for {query}: {record_ids}")  # Отладка
            records = self._load_records_by_ids(collection_path, record_ids)
        else:
            records = self._load_all_records(collection_path)
        print(f"Loaded records: {records}")  # Отладка

        if query:
            records = self._filter_records(records, query)
        print(f"Filtered records: {records}")  # Отладка

        if sort:
            records = self._sort_records(records, sort)

        records = records[skip:]
        if limit is not None:
            records = records[:limit]

        if collection in self.buffer:
            buffered_records = [r for r in (self.storage.decode_record(b) for b in self.buffer[collection]) if r]
            print(f"Buffered records: {buffered_records}")  # Отладка
            filtered_buffered = self._filter_records(buffered_records, query) if query else buffered_records
            records.extend(filtered_buffered)
            if sort:
                records = self._sort_records(records, sort)
            records = records[skip:skip+limit if limit else None]
        print(f"Final records: {records}")  # Отладка

        return records

    def _load_all_records(self, collection_path: str) -> List[Dict]:
        """Loads all records from a collection file.

        Args:
            collection_path (str): Path to the collection file.

        Returns:
            List[Dict]: List of decoded records.
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
                        print(f"Invalid record length at offset {offset}")  # Отладка
                        break
                    record_data = f.read(record_len)
                    if len(record_data) < record_len:
                        print(f"Incomplete record at offset {offset}")  # Отладка
                        break
                    record = self.storage.decode_record(record_data)
                    if record:
                        records.append(record)
                    else:
                        print(f"Failed to decode record at offset {offset}")  # Отладка
                    offset += 4 + record_len
        except (IOError, struct.error) as e:
            print(f"Error loading records: {e}")  # Отладка
            raise FluxDBError(f"Failed to load records: {e}")
        return records

    def _load_records_by_ids(self, collection_path: str, record_ids: Set[str]) -> List[Dict]:
        """Loads records by their IDs.

        Args:
            collection_path (str): Path to the collection file.
            record_ids (Set[str]): Set of record IDs to load.

        Returns:
            List[Dict]: List of matching records.
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
                        print(f"Invalid record length at offset {offset}")  # Отладка
                        break
                    record_data = f.read(record_len)
                    if len(record_data) < record_len:
                        print(f"Incomplete record at offset {offset}")  # Отладка
                        break
                    record = self.storage.decode_record(record_data)
                    if record and record['_id'] in record_ids:
                        records.append(record)
                    offset += 4 + record_len
        except (IOError, struct.error) as e:
            print(f"Error loading records by IDs: {e}")  # Отладка
            raise FluxDBError(f"Failed to load records by IDs: {e}")
        return records

    def _filter_records(self, records: List[Dict], query: Dict) -> List[Dict]:
        """Filters records based on a query.

        Args:
            records (List[Dict]): Records to filter.
            query (Dict): Query dictionary.

        Returns:
            List[Dict]: Filtered records.
        """
        results = []
        for record in records:
            matches = True
            for key, condition in query.items():
                if isinstance(condition, dict):
                    for op, value in condition.items():
                        record_value = record.get(key, "")
                        try:
                            record_num = float(record_value) if record_value else 0
                            if op == '$gt' and not (record_num > value):
                                matches = False
                            elif op == '$lt' and not (record_num < value):
                                matches = False
                            elif op == '$in' and record_value not in value:
                                matches = False
                        except ValueError:
                            matches = False
                elif record.get(key, "") != condition:  # Убрали str(condition)
                    matches = False
                    print(f"Record {record} does not match {key}={condition}")  # Отладка
            if matches:
                results.append(record)
        return results

    def _sort_records(self, records: List[Dict], sort: Dict) -> List[Dict]:
        """Sorts records based on sort criteria.

        Args:
            records (List[Dict]): Records to sort.
            sort (Dict): Sort criteria.

        Returns:
            List[Dict]: Sorted records.
        """
        def key_func(record):
            keys = []
            for field, direction in sort.items():
                value = record.get(field, "")
                try:
                    value = float(value)
                except ValueError:
                    pass
                keys.append((value, direction))
            return keys

        return sorted(records, key=key_func, reverse=any(v == -1 for v in sort.values()))

    def update(self, collection: str, record_id: str, update_data: Dict) -> bool:
        """Updates a record by ID.

        Args:
            collection (str): Name of the collection.
            record_id (str): ID of the record to update.
            update_data (Dict): Data to update.

        Returns:
            bool: True if updated, False if not found.

        Raises:
            CollectionNotFoundError: If the collection does not exist.
        """
        def _update():
            records = self._load_all_records(collection_path)
            updated = False
            updated_record = None
            for record in records:
                if record['_id'] == record_id:
                    record.update(update_data)
                    record['_id'] = record_id  # Сохраняем _id
                    updated = True
                    updated_record = record
                    break
            if updated:
                with open(collection_path, 'wb') as f:
                    for record in records:
                        f.write(self.storage.encode_record(record))
                self.index_manager.update_index(collection, updated_record)
            return updated

        collection_path = self._get_collection_path(collection)
        if not os.path.exists(collection_path):
            raise CollectionNotFoundError(f"Collection {collection} not found")
        self._add_to_transaction(_update)
        return True

    def delete(self, collection: str, record_id: str) -> bool:
        """Deletes a record by ID.

        Args:
            collection (str): Name of the collection.
            record_id (str): ID of the record to delete.

        Returns:
            bool: True if deleted, False if not found.

        Raises:
            CollectionNotFoundError: If the collection does not exist.
        """
        def _delete():
            records = self._load_all_records(collection_path)
            initial_len = len(records)
            records = [r for r in records if r['_id'] != record_id]
            if len(records) < initial_len:
                with open(collection_path, 'wb') as f:
                    for record in records:
                        f.write(self.storage.encode_record(record))
                self.index_manager.remove_from_index(collection, record_id)
                return True
            return False

        collection_path = self._get_collection_path(collection)
        if not os.path.exists(collection_path):
            raise CollectionNotFoundError(f"Collection {collection} not found")
        self._add_to_transaction(_delete)
        return True

    def exists(self, collection: str, record_id: str) -> bool:
        """Checks if a record exists.

        Args:
            collection (str): Name of the collection.
            record_id (str): ID of the record.

        Returns:
            bool: True if the record exists, False otherwise.
        """
        records = self._load_all_records(self._get_collection_path(collection))
        return any(r['_id'] == record_id for r in records)

    def count(self, collection: str, query: Optional[Dict] = None) -> int:
        """Counts records matching a query.

        Args:
            collection (str): Name of the collection.
            query (Optional[Dict]): Query dictionary.

        Returns:
            int: Number of matching records.
        """
        return len(self.find(collection, query))

    def aggregate(self, collection: str, pipeline: List[Dict]) -> List[Dict]:
        """Performs aggregation on a collection.

        Args:
            collection (str): Name of the collection.
            pipeline (List[Dict]): Aggregation pipeline.

        Returns:
            List[Dict]: Aggregated results.
        """
        records = self.find(collection)
        for stage in pipeline:
            if stage.get('$group'):
                group_by = stage['$group']['_id']
                accumulators = {k: v for k, v in stage['$group'].items() if k != '_id'}
                grouped = {}
                for record in records:
                    key = record.get(group_by, None)
                    if key not in grouped:
                        grouped[key] = {'_id': key}
                        for acc_key, acc in accumulators.items():
                            if acc.get('$sum'):
                                grouped[key][acc_key] = 0
                            elif acc.get('$count'):
                                grouped[key][acc_key] = 0
                    for acc_key, acc in accumulators.items():
                        if acc.get('$sum'):
                            try:
                                grouped[key][acc_key] += float(record.get(acc['$sum'], 0))
                            except ValueError:
                                pass
                        elif acc.get('$count'):
                            grouped[key][acc_key] += 1
                records = list(grouped.values())
        return records

    def export_collection(self, collection: str, output_file: str) -> bool:
        """Exports a collection to a file.

        Args:
            collection (str): Name of the collection.
            output_file (str): Path to the output file.

        Returns:
            bool: True if exported, False if not found.
        """
        collection_path = self._get_collection_path(collection)
        if not os.path.exists(collection_path):
            return False
        try:
            self._flush_buffer(collection)  # Сбрасываем буфер перед экспортом
            with open(collection_path, 'rb') as src, open(output_file, 'wb') as dst:
                dst.write(src.read())
            return True
        except IOError as e:
            raise FluxDBError(f"Failed to export collection {collection}: {e}")

    def import_collection(self, collection: str, input_file: str) -> bool:
        """Imports a collection from a file.

        Args:
            collection (str): Name of the collection.
            input_file (str): Path to the input file.

        Returns:
            bool: True if imported, False if file not found.
        """
        if not os.path.exists(input_file):
            return False
        collection_path = self._get_collection_path(collection)
        try:
            with open(input_file, 'rb') as src, open(collection_path, 'wb') as dst:
                dst.write(src.read())
            records = self._load_all_records(collection_path)
            for record in records:
                self.index_manager.update_index(collection, record)
            return True
        except IOError as e:
            raise FluxDBError(f"Failed to import collection {collection}: {e}")
