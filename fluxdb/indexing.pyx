# cython: language_level=3
import os
import json
from typing import Dict, List, Set

class IndexManager:
    def __init__(self, db_path: str):
        """Инициализация менеджера индексов. Использует JSON для текстового формата."""
        self.db_path = db_path
        self.index_path = os.path.join(db_path, "indexes")
        if not os.path.exists(self.index_path):
            os.makedirs(self.index_path)

    def _get_index_path(self, collection: str) -> str:
        """Возвращает путь к файлу индекса."""
        return os.path.join(self.index_path, f"{collection}.idx")

    def create_index(self, collection: str, fields: List[str]):
        """Создает индекс."""
        index_path = self._get_index_path(collection)
        index_data = {field: {} for field in fields}
        with open(index_path, 'w') as f:
            json.dump(index_data, f, indent=2)

    def clear_index(self, collection: str):
        """Очищает индекс."""
        index_path = self._get_index_path(collection)
        if os.path.exists(index_path):
            with open(index_path, 'r') as f:
                index_data = json.load(f)
            for field in index_data:
                index_data[field] = {}
            with open(index_path, 'w') as f:
                json.dump(index_data, f, indent=2)

    def drop_index(self, collection: str):
        """Удаляет индекс."""
        index_path = self._get_index_path(collection)
        if os.path.exists(index_path):
            os.remove(index_path)

    def update_index(self, collection: str, record: Dict):
        """Обновляет индекс."""
        index_path = self._get_index_path(collection)
        if not os.path.exists(index_path):
            return
        with open(index_path, 'r') as f:
            index_data = json.load(f)
        record_id = record['_id']
        for field in index_data:
            value = str(record.get(field, ""))
            if value not in index_data[field]:
                index_data[field][value] = []
            if record_id not in index_data[field][value]:
                index_data[field][value].append(record_id)
        with open(index_path, 'w') as f:
            json.dump(index_data, f, indent=2)

    def remove_from_index(self, collection: str, record_id: str):
        """Удаляет запись из индекса."""
        index_path = self._get_index_path(collection)
        if not os.path.exists(index_path):
            return
        with open(index_path, 'r') as f:
            index_data = json.load(f)
        for field in index_data:
            for value in list(index_data[field]):
                if record_id in index_data[field][value]:
                    index_data[field][value].remove(record_id)
                if not index_data[field][value]:
                    del index_data[field][value]
        with open(index_path, 'w') as f:
            json.dump(index_data, f, indent=2)

    def can_use_index(self, collection: str, query: Dict) -> bool:
        """Проверяет возможность использования индекса."""
        index_path = self._get_index_path(collection)
        if not os.path.exists(index_path):
            return False
        with open(index_path, 'r') as f:
            index_data = json.load(f)
        return any(key in index_data for key in query)

    def query_index(self, collection: str, query: Dict) -> Set[str]:
        """Выполняет поиск по индексу."""
        index_path = self._get_index_path(collection)
        with open(index_path, 'r') as f:
            index_data = json.load(f)
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