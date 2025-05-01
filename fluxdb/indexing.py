import os
import pickle
from typing import Dict, List, Set, Optional
from .exceptions import FluxDBError

class IndexManager:
    """Manages indexes for FluxDB collections, storing them in a binary format using pickle.

    Args:
        db_path (str): Path to the database directory.
    """
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.index_path = os.path.join(db_path, "indexes")
        self._index_cache: Dict[str, Dict] = {}  # In-memory cache for indexes
        os.makedirs(self.index_path, exist_ok=True)

    def _get_index_path(self, collection: str) -> str:
        """Returns the file path for a collection's index."""
        return os.path.join(self.index_path, f"{collection}.idx")

    def create_index(self, collection: str, fields: List[str]) -> None:
        """Creates an index for specified fields in a collection.

        Args:
            collection (str): Name of the collection.
            fields (List[str]): Fields to index.
        """
        index_path = self._get_index_path(collection)
        index_data = {field: {} for field in fields}
        self._index_cache[collection] = index_data
        self._save_index(collection, index_data)

    def clear_index(self, collection: str) -> None:
        """Clears all indexes for a collection.

        Args:
            collection (str): Name of the collection.
        """
        index_path = self._get_index_path(collection)
        if collection in self._index_cache:
            self._index_cache[collection] = {field: {} for field in self._index_cache[collection]}
            self._save_index(collection, self._index_cache[collection])
        elif os.path.exists(index_path):
            with open(index_path, 'rb') as f:
                index_data = pickle.load(f)
            for field in index_data:
                index_data[field] = {}
            self._save_index(collection, index_data)

    def drop_index(self, collection: str) -> None:
        """Drops the index for a collection.

        Args:
            collection (str): Name of the collection.
        """
        index_path = self._get_index_path(collection)
        if collection in self._index_cache:
            del self._index_cache[collection]
        if os.path.exists(index_path):
            os.remove(index_path)

    def update_index(self, collection: str, record: Dict) -> None:
        """Updates the index with a new or modified record.

        Args:
            collection (str): Name of the collection.
            record (Dict): Record to index.
        """
        index_data = self._load_index(collection)
        if not index_data:
            return
        record_id = record['_id']
        for field in index_data:
            value = str(record.get(field, ""))
            if value not in index_data[field]:
                index_data[field][value] = []
            if record_id not in index_data[field][value]:
                index_data[field][value].append(record_id)
        self._index_cache[collection] = index_data
        self._save_index(collection, index_data)

    def remove_from_index(self, collection: str, record_id: str) -> None:
        """Removes a record from the index.

        Args:
            collection (str): Name of the collection.
            record_id (str): ID of the record to remove.
        """
        index_data = self._load_index(collection)
        if not index_data:
            return
        for field in index_data:
            for value in list(index_data[field]):
                if record_id in index_data[field][value]:
                    index_data[field][value].remove(record_id)
                if not index_data[field][value]:
                    del index_data[field][value]
        self._index_cache[collection] = index_data
        self._save_index(collection, index_data)

    def can_use_index(self, collection: str, query: Dict) -> bool:
        """Checks if an index can be used for a query.

        Args:
            collection (str): Name of the collection.
            query (Dict): Query dictionary.

        Returns:
            bool: True if an index can be used, False otherwise.
        """
        index_data = self._load_index(collection)
        return bool(index_data and any(key in index_data for key in query))

    def query_index(self, collection: str, query: Dict) -> Set[str]:
        """Queries the index to retrieve record IDs matching the query.

        Args:
            collection (str): Name of the collection.
            query (Dict): Query dictionary.

        Returns:
            Set[str]: Set of matching record IDs.
        """
        index_data = self._load_index(collection)
        if not index_data:
            return set()
        result_ids = None
        for key, value in query.items():
            if key in index_data:
                value_str = str(value)
                ids = set(index_data[key].get(value_str, []))
                if result_ids is None:
                    result_ids = ids
                else:
                    result_ids = result_ids.intersection(ids)
        return result_ids or set()

    def _load_index(self, collection: str) -> Optional[Dict]:
        """Loads the index for a collection from cache or disk.

        Args:
            collection (str): Name of the collection.

        Returns:
            Optional[Dict]: Index data or None if not found.
        """
        if collection in self._index_cache:
            return self._index_cache[collection]
        index_path = self._get_index_path(collection)
        if os.path.exists(index_path):
            try:
                with open(index_path, 'rb') as f:
                    index_data = pickle.load(f)
                    self._index_cache[collection] = index_data
                    return index_data
            except (pickle.PickleError, EOFError):
                return None
        return None

    def _save_index(self, collection: str, index_data: Dict) -> None:
        """Saves the index to disk.

        Args:
            collection (str): Name of the collection.
            index_data (Dict): Index data to save.
        """
        index_path = self._get_index_path(collection)
        try:
            with open(index_path, 'wb') as f:
                pickle.dump(index_data, f, protocol=pickle.HIGHEST_PROTOCOL)
        except IOError as e:
            raise FluxDBError(f"Failed to save index for {collection}: {e}")
