import os
import psutil
from typing import Optional
from .collection_manager import CollectionManager
from .transaction_manager import TransactionManager
from .data_manager import DataManager
from .buffer_manager import BufferManager
from .indexing import IndexManager
from .storage import BinaryStorage, StorageBackend
from .admin_server import AdminServer

class FluxDB:
    """
    A lightweight file-based NoSQL database with collections, indexing, and transactions.

    Args:
        db_path (str): Path to the database directory.
        storage_backend (StorageBackend, optional): Backend for record encoding/decoding.
        web (bool, optional): If True, starts the web admin server.
        debugweb (bool, optional): If True, enables Flask debug mode and console logs.
        host (str, optional): Host for the web server.
        port (int, optional): Port for the web server.
        admin_password (str, optional): Password for admin login.
        secret_key (str, optional): Secret key for Flask session.
    """
    def __init__(
        self,
        db_path: str,
        storage_backend: Optional[StorageBackend] = None,
        web: bool = False,
        debugweb: bool = False,
        host: str = '0.0.0.0',
        port: int = 5000,
        admin_password: Optional[str] = None,
        secret_key: Optional[str] = None
    ):
        self.db_path = os.path.abspath(db_path)
        available_mem = psutil.virtual_memory().available // 1024 // 1024  # MB
        self.buffer_size = max(100, min(10000, available_mem // 1000))
        self.storage = storage_backend or BinaryStorage()
        self.index_manager = IndexManager(self.db_path)
        self.collection_manager = CollectionManager(self.db_path, self.index_manager)
        self.transaction_manager = TransactionManager()
        self.buffer_manager = BufferManager(self.db_path, self.storage, self.buffer_size)
        self.data_manager = DataManager(self.db_path, self.storage, self.index_manager,
                                       self.buffer_manager, self.transaction_manager)
        os.makedirs(self.db_path, exist_ok=True)
        os.makedirs(os.path.join(self.db_path, 'indexes'), exist_ok=True)
        if web:
            self.admin_server = AdminServer(self.db_path, host, port, debugweb, admin_password, secret_key)
            self.admin_server.start()

    def create_collection(self, collection: str, indexed_fields: Optional[list[str]] = None) -> bool:
        return self.collection_manager.create_collection(collection, indexed_fields)

    def drop_collection(self, collection: str) -> bool:
        return self.collection_manager.drop_collection(collection)

    def clear_collection(self, collection: str) -> bool:
        return self.collection_manager.clear_collection(collection)

    def import_collection(self, collection: str, input_file: str) -> bool:
        return self.collection_manager.import_collection(collection, input_file)

    def export_collection(self, collection: str, output_file: str) -> bool:
        return self.collection_manager.export_collection(collection, output_file)

    def list_collections(self) -> list[str]:
        return self.collection_manager.list_collections()

    def begin_transaction(self) -> None:
        self.transaction_manager.begin_transaction()

    def commit(self) -> None:
        self.transaction_manager.commit(self.buffer_manager)

    def rollback(self) -> None:
        self.transaction_manager.rollback()

    def insert(self, collection: str, data: dict) -> str:
        return self.data_manager.insert(collection, data)

    def insert_many(self, collection: str, data_list: list[dict]) -> list[str]:
        return self.data_manager.insert_many(collection, data_list)

    def find(self, collection: str, query: Optional[dict] = None, limit: Optional[int] = None,
             skip: int = 0, sort: Optional[dict] = None) -> list[dict]:
        return self.data_manager.find(collection, query, limit, skip, sort)

    def update(self, collection: str, record_id: str, update_data: dict) -> bool:
        return self.data_manager.update(collection, record_id, update_data)

    def delete(self, collection: str, record_id: str) -> bool:
        return self.data_manager.delete(collection, record_id)

    def exists(self, collection: str, record_id: str) -> bool:
        return self.data_manager.exists(collection, record_id)

    def count(self, collection: str, query: Optional[dict] = None) -> int:
        return self.data_manager.count(collection, query)

    def aggregate(self, collection: str, pipeline: list[dict]) -> list[dict]:
        return self.data_manager.aggregate(collection, pipeline)
