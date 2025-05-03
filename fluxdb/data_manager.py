import uuid
import os
from typing import Dict, List, Set, Optional
from .exceptions import FluxDBError, CollectionNotFoundError
from .storage import StorageBackend
from .indexing import IndexManager
from .buffer_manager import BufferManager
from .transaction_manager import TransactionManager
from .record_loader import RecordLoader

class DataManager:
    """Manages data operations such as insert, find, update, and delete."""
    
    def __init__(self, db_path: str, storage: StorageBackend, index_manager: IndexManager,
                 buffer_manager: BufferManager, transaction_manager: TransactionManager):
        self.db_path = db_path
        self.storage = storage
        self.index_manager = index_manager
        self.buffer_manager = buffer_manager
        self.transaction_manager = transaction_manager
        self.record_loader = RecordLoader(storage)

    def _get_collection_path(self, collection: str) -> str:
        """Returns the file path for a collection."""
        return os.path.join(self.db_path, f"{collection}.fdb")

    def insert(self, collection: str, data: Dict) -> str:
        """
        Inserts a new record.

        Args:
            collection (str): Name of the collection.
            data (Dict): Record to insert.

        Returns:
            str: ID of the inserted record.

        Raises:
            CollectionNotFoundError: If the collection does not exist.
        """
        record_id = data.get('_id', str(uuid.uuid4()))

        def _insert():
            data_with_id = data.copy()
            data_with_id['_id'] = record_id
            record_bytes = self.storage.encode_record(data_with_id)
            self.buffer_manager.append_to_buffer(collection, record_bytes)
            self.index_manager.update_index(collection, data_with_id)
            if self.buffer_manager.is_buffer_full(collection):
                self.buffer_manager.flush_buffer(collection)

        collection_path = self._get_collection_path(collection)
        if not os.path.exists(collection_path):
            raise CollectionNotFoundError(f"Collection {collection} not found")
        self.transaction_manager.add_to_transaction(_insert)
        return record_id

    def insert_many(self, collection: str, data_list: List[Dict]) -> List[str]:
        """
        Inserts multiple records.

        Args:
            collection (str): Name of the collection.
            data_list (List[Dict]): List of records to insert.

        Returns:
            List[str]: IDs of inserted records.
        """
        return [self.insert(collection, data) for data in data_list]

    def find(self, collection: str, query: Optional[Dict] = None, limit: Optional[int] = None,
             skip: int = 0, sort: Optional[Dict] = None) -> List[Dict]:
        """
        Finds records matching a query.

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

        self.buffer_manager.flush_buffer(collection)

        records = []
        if query and self.index_manager.can_use_index(collection, query):
            record_ids = self.index_manager.query_index(collection, query)
            records = self.record_loader.load_records_by_ids(collection_path, record_ids)
        else:
            records = self.record_loader.load_all_records(collection_path)

        if query:
            records = self._filter_records(records, query)

        if sort:
            records = self._sort_records(records, sort)

        records = records[skip:]
        if limit is not None:
            records = records[:limit]

        return records

    def _filter_records(self, records: List[Dict], query: Dict) -> List[Dict]:
        """
        Filters records based on a query.

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
                elif record.get(key, "") != str(condition):
                    matches = False
            if matches:
                results.append(record)
        return results

    def _sort_records(self, records: List[Dict], sort: Dict) -> List[Dict]:
        """
        Sorts records based on sort criteria.

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
        """
        Updates a record by ID.

        Args:
            collection (str): Name of the collection.
            record_id (str): ID of the record to update.
            update_data (Dict): Data to update.

        Returns:
            bool: True if updated, False if not found.

        Raises:
            CollectionNotFoundError: If the collection does not exist.
            FluxDBError: If file operation fails.
        """
        def _update():
            records = self.record_loader.load_all_records(collection_path)
            updated = False
            updated_record = None
            for record in records:
                if record['_id'] == record_id:
                    record.update(update_data)
                    record['_id'] = record_id
                    updated = True
                    updated_record = record
                    break
            if updated:
                try:
                    with open(collection_path, 'wb') as f:
                        for record in records:
                            f.write(self.storage.encode_record(record))
                    self.index_manager.update_index(collection, updated_record)
                except IOError as e:
                    raise FluxDBError(f"Failed to update collection {collection}: {e}")
            return updated

        collection_path = self._get_collection_path(collection)
        if not os.path.exists(collection_path):
            raise CollectionNotFoundError(f"Collection {collection} not found")
        self.transaction_manager.add_to_transaction(_update)
        return True

    def delete(self, collection: str, record_id: str) -> bool:
        """
        Deletes a record by ID.

        Args:
            collection (str): Name of the collection.
            record_id (str): ID of the record to delete.

        Returns:
            bool: True if deleted, False if not found.

        Raises:
            CollectionNotFoundError: If the collection does not exist.
            FluxDBError: If file operation fails.
        """
        def _delete():
            records = self.record_loader.load_all_records(collection_path)
            initial_len = len(records)
            records = [r for r in records if r['_id'] != record_id]
            if len(records) < initial_len:
                try:
                    with open(collection_path, 'wb') as f:
                        for record in records:
                            f.write(self.storage.encode_record(record))
                    self.index_manager.remove_from_index(collection, record_id)
                    return True
                except IOError as e:
                    raise FluxDBError(f"Failed to delete from collection {collection}: {e}")
            return False

        collection_path = self._get_collection_path(collection)
        if not os.path.exists(collection_path):
            raise CollectionNotFoundError(f"Collection {collection} not found")
        self.transaction_manager.add_to_transaction(_delete)
        return True

    def exists(self, collection: str, record_id: str) -> bool:
        """
        Checks if a record exists.

        Args:
            collection (str): Name of the collection.
            record_id (str): ID of the record.

        Returns:
            bool: True if the record exists, False otherwise.
        """
        try:
            self.buffer_manager.flush_buffer(collection)
            records = self.record_loader.load_all_records(self._get_collection_path(collection))
            return any(r['_id'] == record_id for r in records)
        except FluxDBError:
            return False

    def count(self, collection: str, query: Optional[Dict] = None) -> int:
        """
        Counts records matching a query.

        Args:
            collection (str): Name of the collection.
            query (Optional[Dict]): Query dictionary.

        Returns:
            int: Number of matching records.
        """
        try:
            return len(self.find(collection, query))
        except CollectionNotFoundError:
            return 0

    def aggregate(self, collection: str, pipeline: List[Dict]) -> List[Dict]:
        """
        Performs aggregation on a collection.

        Args:
            collection (str): Name of the collection.
            pipeline (List[Dict]): Aggregation pipeline.

        Returns:
            List[Dict]: Aggregated results.
        """
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
        except CollectionNotFoundError:
            return []
