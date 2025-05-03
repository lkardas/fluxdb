import os
import pickle
from typing import Dict, List, Set, Optional
from .exceptions import FluxDBError


class IndexManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.index_path = os.path.join(db_path, "indexes")
        self._index_cache: Dict[str, Dict] = {}
        os.makedirs(self.index_path, exist_ok=True)

    def _get_index_path(self, collection: str) -> str:
        return os.path.join(self.index_path, f"{collection}.idx")

    def create_index(self, collection: str, fields: List[str]) -> None:
        index_path = self._get_index_path(collection)
        index_data = {field: {} for field in fields}
        self._index_cache[collection] = index_data
        try:
            self._save_index(collection, index_data)
        except IOError as e:
            raise FluxDBError(f"Failed to create index for {collection}: {e}")

    def clear_index(self, collection: str) -> None:
        index_path = self._get_index_path(collection)
        try:
            if collection in self._index_cache:
                self._index_cache[collection] = {field: {} for field in self._index_cache[collection]}
                self._save_index(collection, self._index_cache[collection])
            elif os.path.exists(index_path):
                with open(index_path, 'rb') as f:
                    index_data = pickle.load(f)
                for field in index_data:
                    index_data[field] = {}
                self._save_index(collection, index_data)
        except (IOError, pickle.PickleError) as e:
            raise FluxDBError(f"Failed to clear index for {collection}: {e}")

    def drop_index(self, collection: str) -> None:
        index_path = self._get_index_path(collection)
        try:
            if collection in self._index_cache:
                del self._index_cache[collection]
            if os.path.exists(index_path):
                os.remove(index_path)
        except IOError as e:
            raise FluxDBError(f"Failed to drop index for {collection}: {e}")

    def update_index(self, collection: str, record: Dict) -> None:
        index_data = self._load_index(collection)
        if not index_data:
            return
        record_id = record['_id']
        try:
            for field in index_data:
                value = record.get(field, "")
                value_str = str(value)
                index_data[field].setdefault(value_str, []).append(record_id)
            self._index_cache[collection] = index_data
            self._save_index(collection, index_data)
        except IOError as e:
            raise FluxDBError(f"Failed to update index for {collection}: {e}")

    def remove_from_index(self, collection: str, record_id: str) -> None:
        index_data = self._load_index(collection)
        if not index_data:
            return
        try:
            for field in index_data:
                for value in list(index_data[field]):
                    if record_id in index_data[field][value]:
                        index_data[field][value].remove(record_id)
                    if not index_data[field][value]:
                        del index_data[field][value]
            self._index_cache[collection] = index_data
            self._save_index(collection, index_data)
        except IOError as e:
            raise FluxDBError(f"Failed to remove from index for {collection}: {e}")

    def can_use_index(self, collection: str, query: Dict) -> bool:
        index_data = self._load_index(collection)
        return bool(index_data and any(key in index_data for key in query))

    def query_index(self, collection: str, query: Dict) -> Set[str]:
        index_data = self._load_index(collection)
        if not index_data:
            return set()
        result_ids = None
        for key, value in query.items():
            if key in index_data:
                value_str = str(value)
                index_data[key].setdefault(value_str, [])
                ids = set(index_data[key].get(value_str, []))
                result_ids = ids if result_ids is None else result_ids.intersection(ids)
        return result_ids or set()

    def list_indexes(self, collection: str) -> List[str]:
        index_data = self._load_index(collection)
        return list(index_data.keys()) if index_data else []

    def _load_index(self, collection: str) -> Optional[Dict]:
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
        index_path = self._get_index_path(collection)
        try:
            with open(index_path, 'wb') as f:
                pickle.dump(index_data, f, protocol=pickle.HIGHEST_PROTOCOL)
        except IOError as e:
            raise FluxDBError(f"Failed to save index for {collection}: {e}")
