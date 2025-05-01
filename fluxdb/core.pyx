# cython: language_level=3
import os
import uuid
import struct
import json
from typing import Dict, List, Optional, Callable, Any
from .indexing import IndexManager

class FluxDB:
    def __init__(self, db_path: str, buffer_size: int = 1000):
        """Инициализация базы данных FluxDB."""
        self.db_path = db_path
        self.buffer_size = buffer_size
        self.index_manager = IndexManager(db_path)
        self.buffer = {}
        self.transaction_active = False
        self.transaction_buffer = []
        if not os.path.exists(db_path):
            os.makedirs(db_path)

    def _get_collection_path(self, collection: str) -> str:
        """Возвращает путь к файлу коллекции."""
        return os.path.join(self.db_path, f"{collection}.fdb")

    def create_collection(self, collection: str, indexed_fields: List[str] = None) -> bool:
        """Создает новую коллекцию."""
        collection_path = self._get_collection_path(collection)
        if os.path.exists(collection_path):
            return False
        with open(collection_path, 'wb') as f:
            f.write(b"")
        if indexed_fields:
            self.index_manager.create_index(collection, indexed_fields)
        return True

    def drop_collection(self, collection: str) -> bool:
        """Удаляет коллекцию и индексы."""
        collection_path = self._get_collection_path(collection)
        if not os.path.exists(collection_path):
            return False
        os.remove(collection_path)
        self.index_manager.drop_index(collection)
        return True

    def clear_collection(self, collection: str) -> bool:
        """Очищает коллекцию, сохраняя индексы."""
        collection_path = self._get_collection_path(collection)
        if not os.path.exists(collection_path):
            return False
        with open(collection_path, 'wb') as f:
            f.write(b"")
        self.index_manager.clear_index(collection)
        return True

    def begin_transaction(self):
        """Начинает транзакцию."""
        if self.transaction_active:
            raise ValueError("Transaction already active")
        self.transaction_active = True
        self.transaction_buffer = []

    def commit(self):
        """Подтверждает транзакцию."""
        if not self.transaction_active:
            raise ValueError("No active transaction")
        for op in self.transaction_buffer:
            op['func'](*op['args'], **op['kwargs'])
        self.transaction_buffer = []
        self.transaction_active = False
        self._flush_buffer()

    def rollback(self):
        """Откатывает транзакцию."""
        if not self.transaction_active:
            raise ValueError("No active transaction")
        self.transaction_buffer = []
        self.transaction_active = False

    def _add_to_transaction(self, func: Callable, *args, **kwargs):
        """Добавляет операцию в транзакцию или выполняет сразу."""
        if self.transaction_active:
            self.transaction_buffer.append({'func': func, 'args': args, 'kwargs': kwargs})
        else:
            func(*args, **kwargs)

    def _encode_record(self, data: Dict) -> bytes:
        """Кодирует запись в бинарный формат."""
        record_id = data.get('_id', str(uuid.uuid4()))
        data['_id'] = record_id
        parts = []
        parts.append(struct.pack('!I', len(data)))
        for key, value in data.items():
            key_bytes = str(key).encode('utf-8')
            value_bytes = str(value).encode('utf-8')
            parts.append(struct.pack('!I', len(key_bytes)) + key_bytes +
                         struct.pack('!I', len(value_bytes)) + value_bytes)
        body = b''.join(parts)
        return struct.pack('!I', len(body) + 16) + uuid.UUID(record_id).bytes + body

    def _decode_record(self, data: bytes) -> Optional[Dict]:
        """Декодирует запись из бинарного формата."""
        try:
            if len(data) < 16:
                return None
            record = {}
            record_id = str(uuid.UUID(bytes=data[:16]))
            record['_id'] = record_id
            offset = 16
            if len(data) < offset + 4:
                return None
            num_fields = struct.unpack('!I', data[offset:offset+4])[0]
            offset += 4
            for _ in range(num_fields):
                if len(data) < offset + 4:
                    return None
                key_len = struct.unpack('!I', data[offset:offset+4])[0]
                offset += 4
                if len(data) < offset + key_len:
                    return None
                key = data[offset:offset+key_len].decode('utf-8', errors='ignore')
                offset += key_len
                if len(data) < offset + 4:
                    return None
                value_len = struct.unpack('!I', data[offset:offset+4])[0]
                offset += 4
                if len(data) < offset + value_len:
                    return None
                value = data[offset:offset+value_len].decode('utf-8', errors='ignore')
                offset += value_len
                record[key] = value
            return record
        except (struct.error, ValueError, UnicodeDecodeError):
            return None

    def _flush_buffer(self, collection: str = None):
        """Сбрасывает буфер на диск."""
        collections = [collection] if collection else list(self.buffer.keys())
        for col in collections:
            if col in self.buffer and self.buffer[col]:
                with open(self._get_collection_path(col), 'ab') as f:
                    for record in self.buffer[col]:
                        f.write(record)
                self.buffer[col] = []

    def insert(self, collection: str, data: Dict) -> str:
        """Вставляет новую запись."""
        def _insert():
            record_id = data.get('_id', str(uuid.uuid4()))
            record_bytes = self._encode_record(data)
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
        """Вставляет несколько записей."""
        return [self.insert(collection, data) for data in data_list]

    def find(self, collection: str, query: Dict = None, limit: int = None, skip: int = 0,
             sort: Dict = None) -> List[Dict]:
        """Ищет записи по запросу."""
        collection_path = self._get_collection_path(collection)
        if not os.path.exists(collection_path):
            return []

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
            buffered_records = [r for r in (self._decode_record(b) for b in self.buffer[collection]) if r]
            records.extend(self._filter_records(buffered_records, query))
            if sort:
                records = self._sort_records(records, sort)
            records = records[skip:skip+limit if limit else None]

        return records

    def _load_all_records(self, collection_path: str) -> List[Dict]:
        """Загружает все записи из файла."""
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
                    record = self._decode_record(record_data)
                    if record:
                        records.append(record)
                    offset += 4 + record_len
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"Ошибка чтения базы данных: {e}")
        return records

    def _load_records_by_ids(self, collection_path: str, record_ids: set) -> List[Dict]:
        """Загружает записи по ID."""
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
                    record = self._decode_record(record_data)
                    if record and record['_id'] in record_ids:
                        records.append(record)
                    offset += 4 + record_len
        except FileNotFoundError:
            pass
        return records

    def _filter_records(self, records: List[Dict], query: Dict) -> List[Dict]:
        """Фильтрует записи по запросу."""
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
        """Сортирует записи."""
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
        """Обновляет запись по ID."""
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
                        f.write(self._encode_record(record))
                self.index_manager.update_index(collection, record)
            return updated

        collection_path = self._get_collection_path(collection)
        if not os.path.exists(collection_path):
            return False
        self._add_to_transaction(_update)
        return True

    def delete(self, collection: str, record_id: str) -> bool:
        """Удаляет запись по ID."""
        def _delete():
            records = self._load_all_records(collection_path)
            initial_len = len(records)
            records = [r for r in records if r['_id'] != record_id]
            if len(records) < initial_len:
                with open(collection_path, 'wb') as f:
                    for record in records:
                        f.write(self._encode_record(record))
                self.index_manager.remove_from_index(collection, record_id)
                return True
            return False

        collection_path = self._get_collection_path(collection)
        if not os.path.exists(collection_path):
            return False
        self._add_to_transaction(_delete)
        return True

    def exists(self, collection: str, record_id: str) -> bool:
        """Проверяет существование записи."""
        records = self._load_all_records(self._get_collection_path(collection))
        return any(r['_id'] == record_id for r in records)

    def count(self, collection: str, query: Dict = None) -> int:
        """Подсчитывает количество записей."""
        return len(self.find(collection, query))

    def aggregate(self, collection: str, pipeline: List[Dict]) -> List[Dict]:
        """Выполняет агрегацию."""
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
        """Экспортирует коллекцию."""
        collection_path = self._get_collection_path(collection)
        if not os.path.exists(collection_path):
            return False
        with open(collection_path, 'rb') as src, open(output_file, 'wb') as dst:
            dst.write(src.read())
        return True

    def import_collection(self, collection: str, input_file: str) -> bool:
        """Импортирует коллекцию."""
        if not os.path.exists(input_file):
            return False
        collection_path = self._get_collection_path(collection)
        with open(input_file, 'rb') as src, open(collection_path, 'wb') as dst:
            dst.write(src.read())
        records = self._load_all_records(collection_path)
        for record in records:
            self.index_manager.update_index(collection, record)
        return True