import os
from typing import Optional, List
from .exceptions import FluxDBError
from .indexing import IndexManager

class CollectionManager:
    """Manages database collections, including creation, deletion, and import/export."""
    
    def __init__(self, db_path: str, index_manager: IndexManager):
        self.db_path = db_path
        self.index_manager = index_manager

    def _get_collection_path(self, collection: str) -> str:
        """Returns the file path for a collection."""
        return os.path.join(self.db_path, f"{collection}.fdb")

    def create_collection(self, collection: str, indexed_fields: Optional[List[str]] = None) -> bool:
        """
        Creates a new collection.

        Args:
            collection (str): Name of the collection.
            indexed_fields (Optional[List[str]]): Fields to index.

        Returns:
            bool: True if created, False if already exists.

        Raises:
            ValueError: If collection name is empty.
            FluxDBError: If file operation fails.
        """
        if not collection:
            raise ValueError("Collection name cannot be empty")
        collection_path = self._get_collection_path(collection)
        if os.path.exists(collection_path):
            return False
        try:
            with open(collection_path, 'wb') as f:
                f.write(b"")
            if indexed_fields:
                self.index_manager.create_index(collection, indexed_fields)
            return True
        except IOError as e:
            raise FluxDBError(f"Failed to create collection {collection}: {e}")

    def drop_collection(self, collection: str) -> bool:
        """
        Drops a collection and its indexes.

        Args:
            collection (str): Name of the collection.

        Returns:
            bool: True if dropped, False if not found.

        Raises:
            FluxDBError: If file operation fails.
        """
        collection_path = self._get_collection_path(collection)
        if not os.path.exists(collection_path):
            return False
        try:
            os.remove(collection_path)
            self.index_manager.drop_index(collection)
            return True
        except IOError as e:
            raise FluxDBError(f"Failed to drop collection {collection}: {e}")

    def clear_collection(self, collection: str) -> bool:
        """
        Clears a collection, preserving its indexes.

        Args:
            collection (str): Name of the collection.

        Returns:
            bool: True if cleared, False if not found.

        Raises:
            FluxDBError: If file operation fails.
        """
        collection_path = self._get_collection_path(collection)
        if not os.path.exists(collection_path):
            return False
        try:
            with open(collection_path, 'wb') as f:
                f.write(b"")
            self.index_manager.clear_index(collection)
            return True
        except IOError as e:
            raise FluxDBError(f"Failed to clear collection {collection}: {e}")

    def export_collection(self, collection: str, output_file: str) -> bool:
        """
        Exports a collection to a file.

        Args:
            collection (str): Name of the collection.
            output_file (str): Path to the output file.

        Returns:
            bool: True if exported, False if not found.

        Raises:
            FluxDBError: If file operation fails.
        """
        collection_path = self._get_collection_path(collection)
        if not os.path.exists(collection_path):
            return False
        try:
            with open(collection_path, 'rb') as src, open(output_file, 'wb') as dst:
                dst.write(src.read())
            return True
        except IOError as e:
            raise FluxDBError(f"Failed to export collection {collection}: {e}")

    def import_collection(self, collection: str, input_file: str) -> bool:
        """
        Imports a collection from a file.

        Args:
            collection (str): Name of the collection.
            input_file (str): Path to the input file.

        Returns:
            bool: True if imported, False if file not found.

        Raises:
            FluxDBError: If file operation fails.
        """
        if not os.path.exists(input_file):
            return False
        collection_path = self._get_collection_path(collection)
        try:
            with open(input_file, 'rb') as src, open(collection_path, 'wb') as dst:
                dst.write(src.read())
            return True
        except IOError as e:
            raise FluxDBError(f"Failed to import collection {collection}: {e}")

    def list_collections(self) -> List[str]:
        """
        Returns a list of all collections in the database.

        Returns:
            List[str]: Names of collections.
        """
        collections = []
        for file in os.listdir(self.db_path):
            if file.endswith('.fdb'):
                collections.append(file[:-4])  # Remove '.fdb'
        return sorted(collections)
