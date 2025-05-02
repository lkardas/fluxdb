import os
import uuid
import struct
import psutil
import logging
import threading
from typing import Dict, List, Set, Optional, Callable, Any
from collections import OrderedDict
from .indexing import IndexManager
from .storage import BinaryStorage, StorageBackend
from .exceptions import FluxDBError, CollectionNotFoundError, TransactionError
from .admin import start_admin_server

# Configure logging to only show warnings and errors
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FluxDB:
    """A lightweight file-based NoSQL database with collections, indexing, and transactions.

    Args:
        db_path (str): Path to the database directory.
        storage_backend (StorageBackend, optional): Backend for record encoding/decoding.
        web (bool, optional): If True, starts the web admin server.
        debugweb (bool, optional): If True, enables Flask debug mode and console logs.
        host (str, optional): Host for the web server.
        port (int, optional): Port for the web server.
    """
    def __init__(self, db_path: str, storage_backend: StorageBackend = None, web: bool = False, 
                 debugweb: bool = False, host: str = '0.0.0.0', port: int = 5000):
        self.db_path = db_path
        # Set buffer size with a safer range
        available_mem = psutil.virtual_memory().available // 1024 // 1024  # MB
        self.buffer_size = max(100, min(5000, available_mem // 1000))  # Reduced max to 5GB
        self.storage = storage_backend or BinaryStorage()
        self.index_manager = IndexManager(db_path)
        self.buffer: Dict[str, List[bytes]] = {}
        self.transaction_active = False
        self.transaction_buffer: List[Dict] = []
        self.file_locks: Dict[str, threading.Lock] = {}  # Per-collection file locks
        self.schema: Dict[str, Dict] = {}  # Optional schema definitions
        # Simple LRU cache for records (max 1000 records)
        self.cache = OrderedDict()  # Maps (collection, record_id) to record
        self.cache_size = 1000
        os.makedirs(db_path, exist_ok=True)
        os.makedirs(os.path.join(db_path, 'indexes'), exist_ok=True)
        if web:
            start_admin_server(db_path, host, port, debugweb)

    def _get_collection_path(self, collection: str) -> str:
        """Returns the file path for a collection."""
        return os.path.join(self.db_path, f"{collection}.fdb")

    def _get_file_lock(self, collection: str) -> threading.Lock:
        """Returns a thread-safe lock for a collection."""
        if collection not in self.file_locks:
            self.file_locks[collection] = threading.Lock()
        return self.file_locks[collection]

    def define_schema(self, collection: str, schema: Dict[str, type]) -> None:
        """Defines a schema for a collection (optional).

        Args:
            collection (str): Name of the collection.
            schema (Dict[str, type]): Field names and their expected types.
        """
        self.schema[collection] = schema

    def create_collection(self, collection: str, indexed_fields: Optional[List[str]] = None,
                         schema: Optional[Dict[str, type]] = None) -> bool:
        """Creates a new collection with optional schema.

        Args:
            collection (str): Name of the collection.
            indexed_fields (Optional[List[str]]): Fields to index.
            schema (Optional[Dict[str, type]]): Schema for validation.

        Returns:
            bool: True if created, False if already exists.
        """
        if not collection:
            raise ValueError("Collection name cannot be empty")
        collection_path = self._get_collection_path(collection)
        if os.path.exists(collection_path):
            return False
        try:
            with self._get_file_lock(collection):
                with open(collection_path, 'wb') as f:
                    f.write(b"")
            if indexed_fields:
                self.index_manager.create_index(collection, indexed_fields)
            if schema:
                self.define_schema(collection, schema)
            return True
        except IOError as e:
            raise FluxDBError(f"Failed to create collection {collection}: {e}")

    def drop_collection(self, collection: str) -> bool:
        """Drops a collection and its indexes."""
        collection_path = self._get_collection_path(collection)
        if not os.path.exists(collection_path):
            return False
        try:
            with self._get_file_lock(collection):
                os.remove(collection_path)
            self.index_manager.drop_index(collection)
            if collection in self.buffer:
                del self.buffer[collection]
            if collection in self.schema:
                del self.schema[collection]
            # Clear cache for this collection
            for key in list(self.cache.keys()):
                if key[0] == collection:
                    del self.cache[key]
            return True
        except IOError as e:
            raise FluxDBError(f"Failed to drop collection {collection}: {e}")

    def clear_collection(self, collection: str) -> bool:
        """Clears a collection, preserving its indexes and schema."""
        collection_path = self._get_collection_path(collection)
        if not os.path.exists(collection_path):
            return False
        try:
            with self._get_file_lock(collection):
                with open(collection_path, 'wb') as f:
                    f.write(b"")
            self.index_manager.clear_index(collection)
            if collection in self.buffer:
                self.buffer[collection] = []
            # Clear cache for this collection
            for key in list(self.cache.keys()):
                if key[0] == collection:
                    del self.cache[key]
            return True
        except IOError as e:
            raise FluxDBError(f"Failed to clear collection {collection}: {e}")

    def begin_transaction(self) -> None:
        """Begins a transaction."""
        if self.transaction_active:
            raise TransactionError("Transaction already active")
        self.transaction_active = True
        self.transaction_buffer = []
        self.transaction_state = {
            'buffer': self.buffer.copy(),  # Snapshot of buffer
            'indexes': self.index_manager.get_state()  # Snapshot of indexes
        }

    def commit(self) -> None:
        """Commits a transaction."""
        if not self.transaction_active:
            raise TransactionError("No active transaction")
        try:
            for op in self.transaction_buffer:
                op['func'](*op['args'], **op['kwargs'])
            self.transaction_buffer = []
            self.transaction_active = False
            self.transaction_state = None
            self._flush_buffer()
        except Exception as e:
            self.rollback()
            raise TransactionError(f"Failed to commit transaction: {e}")

    def rollback(self) -> None:
        """Rolls back a transaction, restoring buffer and indexes."""
        if not self.transaction_active:
            raise TransactionError("No active transaction to roll back")
        self.buffer = self.transaction_state['buffer']
        self.index_manager.restore_state(self.transaction_state['indexes'])
        self.transaction_buffer = []
        self.transaction_active = False
        self.transaction_state = None

    def _add_to_transaction(self, func: Callable, *args, **kwargs) -> None:
        """Adds an operation to a transaction or executes it immediately."""
        if self.transaction_active:
            self.transaction_buffer.append({'func': func, 'args': args, 'kwargs': kwargs})
        else:
            func(*args, **kwargs)

    def _flush_buffer(self, collection: Optional[str] = None) -> None:
        """Flushes the in-memory buffer to disk with batch writes."""
        collections = [collection] if collection else list(self.buffer.keys())
        for col in collections:
            if col in self.buffer and self.buffer[col]:
                try:
                    collection_path = self._get_collection_path(col)
                    with self._get_file_lock(col):
                        with open(collection_path, 'ab') as f:
                            # Batch write to reduce I/O calls
                            f.writelines(self.buffer[col])
                    self.buffer[col] = []
                except IOError as e:
                    raise FluxDBError(f"Failed to flush buffer for {col}: {e}")

    def _validate_record(self, collection: str, data: Dict) -> None:
        """Validates a record against the collection's schema, if defined."""
        if collection in self.schema:
            schema = self.schema[collection]
            for field, field_type in schema.items():
                if field in data and not isinstance(data[field], field_type):
                    raise ValueError(f"Field {field} in {collection} must be {field_type}, got {type(data[field])}")

    def insert(self, collection: str, data: Dict) -> str:
        """Inserts a new record with schema validation."""
        record_id = data.get('_id', str(uuid.uuid4()))

        def _insert():
            data_with_id = data.copy()
            data_with_id['_id'] = record_id
            self._validate_record(collection, data_with_id)
            record_bytes = self.storage.encode_record(data_with_id)
            if collection not in self.buffer:
                self.buffer[collection] = []
            self.buffer[collection].append(record_bytes)
            self.index_manager.update_index(collection, data_with_id)
            # Update cache
            cache_key = (collection, record_id)
            self.cache[cache_key] = data_with_id
            if len(self.cache) > self.cache_size:
                self.cache.popitem(last=False)
            if len(self.buffer[collection]) >= self.buffer_size:
                self._flush_buffer(collection)

        collection_path = self._get_collection_path(collection)
        if not os.path.exists(collection_path):
            self.create_collection(collection)
        self._add_to_transaction(_insert)
        return record_id

    def insert_many(self, collection: str, data_list: List[Dict]) -> List[str]:
        """Inserts multiple records with batch optimization."""
        record_ids = []

        def _insert_many():
            if collection not in self.buffer:
                self.buffer[collection] = []
            for data in data_list:
                record_id = data.get('_id use record_id
                data_with_id = data.copy()
                data_with_id['_id'] = record_id
                self._validate_record(collection, data_with_id)
                record_bytes = self.storage.encode_record(data_with_id)
                self.buffer[collection].append(record_bytes)
                self.index_manager.update_index(collection, data_with_id)
                # Update cache
                cache_key = (collection, record_id)
                self.cache[cache_key] = data_with_id
                if len(self.cache) > self.cache_size:
                    self.cache.popitem(last=False)
                record_ids.append(record_id)
            if len(self.buffer[collection]) >= self.buffer_size:
                self._flush_buffer(collection)

        collection_path = self._get_collection_path(collection)
        if not os.path.exists(collection_path):
            self.create_collection(collection)
        self._add_to_transaction(_insert_many)
        return record_ids

    def find(self, collection: str, query: Optional[Dict] = None, limit: Optional[int] = None,
             skip: int = 0, sort: Optional[Dict] = None) -> List[Dict]:
        """Finds records with enhanced query support."""
        collection_path = self._get_collection_path(collection)
        if not os.path.exists(collection_path):
            raise CollectionNotFoundError(f"Collection {collection} not found")

        self._flush_buffer(collection)
        records = []

        # Check cache first
        if query and '_id' in query and isinstance(query['_id'], str):
            cache_key = (collection, query['_id'])
            if cache_key in self.cache:
                records = [self.cache[cache_key]]
                if self._filter_records(records, query):  # Still apply other query conditions
                    return records[:limit] if limit else records

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

        # Update cache
        for record in records:
            cache_key = (collection, record['_id'])
            self.cache[cache_key] = record
            if len(self.cache) > self.cache_size:
                self.cache.popitem(last=False)

        return records

    def _load_all_records(self, collection_path: str) -> List[Dict]:
        """Loads all records, skipping corrupted ones."""
        records = []
        try:
            with open(collection_path, 'rb') as f:
                file_size = os.path.getsize(collection_path)
                offset = 0
                while offset < file_size:
                    f.seek(offset)
                    len_bytes = f.read(4)
                    if len(len_bytes) < 4:
                        logger.warning(f"Corrupted record at offset {offset} in {collection_path}")
                        break
                    record_len = struct.unpack('!I', len_bytes)[0]
                    if offset + 4 + record_len > file_size:
                        logger.warning(f"Truncated record at offset {offset} in {collection_path}")
                        break
                    record_data = f.read(record_len)
                    if len(record_data) < record_len:
                        logger.warning(f"Incomplete record at offset {offset} in {collection_path}")
                        break
                    try:
                        record = self.storage.decode_record(record_data)
                        if record:
                            records.append(record)
                    except Exception as e:
                        logger.warning(f"Failed to decode record at offset {offset}: {e}")
                    offset += 4 + record_len
        except (IOError, struct.error) as e:
            raise FluxDBError(f"Failed to load records: {e}")
        return records

    def _load_records_by_ids(self, collection_path: str, record_ids: Set[str]) -> List[Dict]:
        """Loads records by IDs, using cache where possible."""
        records = []
        cached_ids = set()
        for record_id in record_ids:
            cache_key = (collection_path, record_id)
            if cache_key in self.cache:
                records.append(self.cache[cache_key])
                cached_ids.add(record_id)
        record_ids = record_ids - cached_ids
        if not record_ids:
            return records
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
                    try:
                        record = self.storage.decode_record(record_data)
                        if record and record['_id'] in record_ids:
                            records.append(record)
                            cache_key = (collection_path, record['_id'])
                            self.cache[cache_key] = record
                            if len(self.cache) > self.cache_size:
                                self.cache.popitem(last=False)
                    except Exception as e:
                        logger.warning(f"Failed to decode record at offset {offset}: {e}")
                    offset += 4 + record_len
        except (IOError, struct.error) as e:
            raise FluxDBError(f"Failed to load records by IDs: {e}")
        return records

    def _filter_records(self, records: List[Dict], query: Dict) -> List[Dict]:
        """Filters records with support for $or, $and, $regex."""
        import re
        results = []
        for record in records:
            matches = True
            for key, condition in query.items():
                record_value = record.get(key, "")
                if isinstance(condition, dict):
                    for op, value in condition.items():
                        try:
                            if op == '$gt':
                                record_num = float(record_value) if record_value else 0
                                matches = matches and (record_num > value)
                            elif op == '$lt':
                                record_num = float(record_value) if record_value else 0
                                matches = matches and (record_num < value)
                            elif op == '$in':
                                matches = matches and (record_value in value)
                            elif op == '$regex':
                                matches = matches and bool(re.match(value, str(record_value)))
                            elif op == '$or':
                                matches = matches and any(self._filter_records([record], sub_query) for sub_query in value)
                            elif op == '$and':
                                matches = matches and all(self._filter_records([record], sub_query) for sub_query in value)
                        except (ValueError, TypeError):
                            matches = False
                elif str(record_value) != str(condition):
                    matches = False
            if matches:
                results.append(record)
        return results

    def _sort_records(self, records: List[Dict], sort: Dict) -> List[Dict]:
        """Sorts records without unnecessary type conversions."""
        def key_func(record):
            keys = []
            for field, direction in sort.items():
                value = record.get(field, "")
                keys.append((value, direction))
            return keys
        return sorted(records, key=key_func, reverse=any(v == -1 for v in sort.values()))

    def update(self, collection: str, record_id: str, update_data: Dict, upsert: bool = False) -> bool:
        """Updates a record with support for $set, $unset, $inc."""
        def _update():
            records = self._load_all_records(collection_path)
            updated = False
            updated_record = None
            for record in records:
                if record['_id'] == record_id:
                    # Handle update operators
                    for key, value in update_data.items():
                        if key == '$set':
                            record.update(value)
                        elif key == '$unset':
                            for field in value:
                                record.pop(field, None)
                        elif key == '$inc':
                            for field, inc in value.items():
                                try:
                                    record[field] = float(record.get(field, 0)) + inc
                                except (ValueError, TypeError):
                                    pass
                    record['_id'] = record_id
                    self._validate_record(collection, record)
                    updated = True
                    updated_record = record
                    break
            if not updated and upsert:
                # Perform upsert
                new_record = {'_id': record_id}
                for key, value in update_data.get('$set', {}).items():
                    new_record[key] = value
                self._validate_record(collection, new_record)
                records.append(new_record)
                updated = True
                updated_record = new_record
            if updated:
                try:
                    with self._get_file_lock(collection):
                        with open(collection_path, 'wb') as f:
                            for record in records:
                                f.write(self.storage.encode_record(record))
                    self.index_manager.update_index(collection, updated_record)
                    # Update cache
                    cache_key = (collection, record_id)
                    self.cache[cache_key] = updated_record
                    if len(self.cache) > self.cache_size:
                        self.cache.popitem(last=False)
                except IOError as e:
                    raise FluxDBError(f"Failed to update collection {collection}: {e}")
            return updated

        collection_path = self._get_collection_path(collection)
        if not os.path.exists(collection_path):
            raise CollectionNotFoundError(f"Collection {collection} not found")
        self._add_to_transaction(_update)
        return True

    def delete(self, collection: str, record_id: str) -> bool:
        """Deletes a record by ID."""
        def _delete():
            records = self._load_all_records(collection_path)
            initial_len = len(records)
            records = [r for r in records if r['_id'] != record_id]
            if len(records) < initial_len:
                try:
                    with self._get_file_lock(collection):
                        with open(collection_path, 'wb') as f:
                            for record in records:
                                f.write(self.storage.encode_record(record))
                    self.index_manager.remove_from_index(collection, record_id)
                    # Remove from cache
                    cache_key = (collection, record_id)
                    self.cache.pop(cache_key, None)
                    return True
                except IOError as e:
                    raise FluxDBError(f"Failed to delete from collection {collection}: {e}")
            return False

        collection_path = self._get_collection_path(collection)
        if not os.path.exists(collection_path):
            raise CollectionNotFoundError(f"Collection {collection} not found")
        self._add_to_transaction(_delete)
        return True

    def add_field(self, collection: str, field: str, default_value: Any) -> bool:
        """Adds a new field to all records in a collection."""
        collection_path = self._get_collection_path(collection)
        if not os.path.exists(collection_path):
            return False
        try:
            records = self._load_all_records(collection_path)
            for record in records:
                if field not in record:
                    record[field] = default_value
            with self._get_file_lock(collection):
                with open(collection_path, 'wb') as f:
                    for record in records:
                        f.write(self.storage.encode_record(record))
            for record in records:
                self.index_manager.update_index(collection, record)
            # Update cache
            for record in records:
                cache_key = (collection, record['_id'])
                self.cache[cache_key] = record
                if len(self.cache) > self.cache_size:
                    self.cache.popitem(last=False)
            return True
        except IOError as e:
            raise FluxDBError(f"Failed to add field to {collection}: {e}")

    def remove_field(self, collection: str, field: str) -> bool:
        """Removes a field from all records in a collection."""
        collection_path = self._get_collection_path(collection)
        if not os.path.exists(collection_path):
            return False
        try:
            records = self._load_all_records(collection_path)
            for record in records:
                record.pop(field, None)
            with self._get_file_lock(collection):
                with open(collection_path, 'wb') as f:
                    for record in records:
                        f.write(self.storage.encode_record(record))
            for record in records:
                self.index_manager.update_index(collection, record)
            # Update cache
            for record in records:
                cache_key = (collection, record['_id'])
                self.cache[cache_key] = record
                if len(self.cache) > self.cache_size:
                    self.cache.popitem(last=False)
            return True
        except IOError as e:
            raise FluxDBError(f"Failed to remove field from {collection}: {e}")

    def rename_field(self, collection: str, old_field: str, new_field: str) -> bool:
        """Renames a field in all records in a collection."""
        collection_path = self._get_collection_path(collection)
        if not os.path.exists(collection_path):
            return False
        try:
            records = self._load_all_records(collection_path)
            for record in records:
                if old_field in record:
                    record[new_field] = record.pop(old_field)
            with self._get_file_lock(collection):
                with open(collection_path, 'wb') as f:
                    for record in records:
                        f.write(self.storage.encode_record(record))
            for record in records:
                self.index_manager.update_index(collection, record)
            # Update cache
            for record in records:
                cache_key = (collection, record['_id'])
                self.cache[cache_key] = record
                if len(self.cache) > self.cache_size:
                    self.cache.popitem(last=False)
            return True
        except IOError as e:
            raise FluxDBError(f"Failed to rename field in {collection}: {e}")

    def exists(self, collection: str, record_id: str) -> bool:
        """Checks if a record exists, using cache if available."""
        cache_key = (collection, record_id)
        if cache_key in self.cache:
            return True
        try:
            self._flush_buffer(collection)
            records = self._load_all_records(self._get_collection_path(collection))
            return any(r['_id'] == record_id for r in records)
        except FluxDBError:
            return False

    def count(self, collection: str, query: Optional[Dict] = None) -> int:
        """Counts records matching a query."""
        try:
            return len(self.find(collection, query))
        except CollectionNotFoundError:
            return 0

    def aggregate(self, collection: str, pipeline: List[Dict]) -> List[Dict]:
        """Performs aggregation with enhanced operator support."""
        try:
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
                                if acc.get('$sum') or acc.get('$avg'):
                                    grouped[key][acc_key] = []
                                elif acc.get('$count'):
                                    grouped[key][acc_key] = 0
                                elif acc.get('$min') or acc.get('$max'):
                                    grouped[key][acc_key] = None
                        for acc_key, acc in accumulators.items():
                            if acc.get('$sum') or acc.get('$avg'):
                                try:
                                    grouped[key][acc_key].append(float(record.get(acc.get('$sum', acc.get('$avg')), 0)))
                                except ValueError:
                                    pass
                            elif acc.get('$count'):
                                grouped[key][acc_key] += 1
                            elif acc.get('$min'):
                                val = record.get(acc['$min'], None)
                                if val is not None:
                                    try:
                                        val = float(val)
                                        if grouped[key][acc_key] is None or val < grouped[key][acc_key]:
                                            grouped[key][acc_key] = val
                                    except ValueError:
                                        pass
                            elif acc.get('$max'):
                                val = record.get(acc['$max'], None)
                                if val is not None:
                                    try:
                                        val = float(val)
                                        if grouped[key][acc_key] is None or val > grouped[key][acc_key]:
                                            grouped[key][acc_key] = val
                                    except ValueError:
                                        pass
                    # Post-process for $avg
                    for key, group in grouped.items():
                        for acc_key, acc in accumulators.items():
                            if acc.get('$avg'):
                                values = group[acc_key]
                                group[acc_key] = sum(values) / len(values) if values else 0
                    records = list(grouped.values())
            return records
        except CollectionNotFoundError:
            return []

    def export_collection(self, collection: str, output_file: str) -> bool:
        """Exports a collection to a file."""
        collection_path = self._get_collection_path(collection)
        if not os.path.exists(collection_path):
            return False
        try:
            self._flush_buffer(collection)
            with self._get_file_lock(collection):
                with open(collection_path, 'rb') as src, open(output_file, 'wb') as dst:
                    dst.write(src.read())
            return True
        except IOError as e:
            raise FluxDBError(f"Failed to export collection {collection}: {e}")

    def import_collection(self, collection: str, input_file: str) -> bool:
        """Imports a collection from a file."""
        if not os.path.exists(input_file):
            return False
        collection_path = self._get_collection_path(collection)
        try:
            with self._get_file_lock(collection):
                with open(input_file, 'rb') as src, open(collection_path, 'wb') as dst:
                    dst.write(src.read())
            records = self._load_all_records(collection_path)
            for record in records:
                self._validate_record(collection, record)
                self.index_manager.update_index(collection, record)
            return True
        except IOError as e:
            raise FluxDBError(f"Failed to import collection {collection}: {e}")

    def list_collections(self) -> List[str]:
        """Returns a list of all collections."""
        collections = []
        for file in os.listdir(self.db_path):
            if file.endswith('.fdb'):
                collections.append(file[:-4])
        return sorted(collections)

    def describe_collection(self, collection: str) -> Dict:
        """Returns metadata about a collection."""
        collection_path = self._get_collection_path(collection)
        if not os.path.exists(collection_path):
            raise CollectionNotFoundError(f"Collection {collection} not found")
        indexed_fields = self.index_manager.get_indexed_fields(collection)
        schema = self.schema.get(collection, {})
        record_count = self.count(collection)
        return {
            'name': collection,
            'indexed_fields': indexed_fields,
            'schema': schema,
            'record_count': record_count,
            'file_size': os.path.getsize(collection_path)
        }

    def start_admin_server(self, host: str = '0.0.0.0', port: int = 5000, debugweb: bool = False) -> None:
        """Starts the web admin server."""
        start_admin_server(self.db_path, host, port, debugweb)
