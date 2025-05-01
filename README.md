
---

# FluxDB

FluxDB is a lightweight, file-based NoSQL database library for Python, designed for persistence without external DBMS dependencies. It provides collections, indexing, transactions, and binary storage with a simple query language, making it ideal for prototyping and embedded systems.

**Note**: FluxDB is a standalone NoSQL database and is not affiliated with InfluxDB.

**Navigation**: [Features](#features) | [Installation](#installation) | [Quick Start](#quick-start) | [API](#api) | [Query Language](#query-language) | [Roadmap](#roadmap) | [License](#license)

## Features

- **Collections**: Organize data with create, drop, and clear operations.
- **Indexing**: Pickle-based indexes for fast queries on specified fields.
- **Transactions**: Atomic operations with begin, commit, and rollback support.
- **Buffering**: In-memory buffering with dynamic flush size based on system memory.
- **Binary Storage**: Compact on-disk format using UUIDs for record IDs and struct-based encoding.
- **Query Language**: Supports exact match, comparison (`$gt`, `$lt`), and list-based (`$in`) queries with sorting and pagination.
- **Import/Export**: Binary dump and restore of collections with automatic index rebuilding.
- **Minimal Dependencies**: Requires only `psutil` for memory management.

## Installation

FluxDB is not yet available on PyPI. Install from source:

    git clone https://github.com/lkardas/fluxdb.git
    cd fluxdb
    pip install .

**Requirements**:
- Python 3.9 or higher
- `psutil>=5.9.0` (installed automatically)

Import in your project:

    from fluxdb import FluxDB

## Quick Start

Get started with FluxDB in a few lines of code:

    from fluxdb import FluxDB

    # Initialize database in the "data" directory
    db = FluxDB("data")

    # Create a collection with indexed fields
    db.create_collection("users", indexed_fields=["age", "status"])

    # Insert a record
    user_id = db.insert("users", {"name": "Alice", "age": 30, "status": "active"})

    # Query records
    results = db.find(
        "users",
        query={"age": {"$gt": 20}},
        sort={"age": 1},
        limit=10
    )
    print(results)  # [{'_id': '...', 'name': 'Alice', 'age': '30', 'status': 'active'}]

    # Update a record
    db.update("users", user_id, {"status": "inactive"})

    # Delete a record
    db.delete("users", user_id)

## API

**Navigation**: [Initialization](#initialization) | [Collection Management](#collection-management) | [Data Operations](#data-operations) | [Transactions](#transactions) | [Aggregation](#aggregation) | [Import/Export](#importexport)

### Initialization

#### `FluxDB(db_path: str, storage_backend: StorageBackend = None)`

Initializes a new FluxDB instance.

- **Parameters**:
  - `db_path`: Directory for storing `.fdb` files and indexes.
  - `storage_backend`: Optional custom storage backend (defaults to `BinaryStorage`).
- **Returns**: A `FluxDB` instance.
- **Raises**: None.

**Example**:

    db = FluxDB("data")

### Collection Management

#### `create_collection(collection: str, indexed_fields: List[str] = None) -> bool`

Creates a new collection, optionally with indexed fields.

- **Parameters**:
  - `collection`: Name of the collection.
  - `indexed_fields`: List of fields to index (e.g., `["age", "status"]`).
- **Returns**: `True` if created, `False` if the collection exists.
- **Raises**:
  - `FluxDBError`: If creation fails due to I/O issues.

**Example**:

    db.create_collection("users", indexed_fields=["age", "status"])

#### `drop_collection(collection: str) -> bool`

Drops a collection and its indexes.

- **Parameters**:
  - `collection`: Name of the collection.
- **Returns**: `True` if dropped, `False` if not found.
- **Raises**:
  - `FluxDBError`: If dropping fails due to I/O issues.

**Example**:

    db.drop_collection("users")

#### `clear_collection(collection: str) -> bool`

Clears all records in a collection, preserving indexes.

- **Parameters**:
  - `collection`: Name of the collection.
- **Returns**: `True` if cleared, `False` if not found.
- **Raises**:
  - `FluxDBError`: If clearing fails due to I/O issues.

**Example**:

    db.clear_collection("users")

### Data Operations

#### `insert(collection: str, data: Dict) -> str`

Inserts a single record with a UUID-based `_id`.

- **Parameters**:
  - `collection`: Name of the collection.
  - `data`: Dictionary containing the record data.
- **Returns**: The `_id` (UUID) of the inserted record.
- **Raises**:
  - `FluxDBError`: If encoding or I/O fails.
  - `CollectionNotFoundError`: If the collection does not exist (auto-created).

**Example**:

    user_id = db.insert("users", {"name": "Alice", "age": 30, "status": "active"})

#### `insert_many(collection: str, data_list: List[Dict]) -> List[str]`

Inserts multiple records.

- **Parameters**:
  - `collection`: Name of the collection.
  - `data_list`: List of dictionaries containing record data.
- **Returns**: List of `_id`s for the inserted records.
- **Raises**:
  - `FluxDBError`: If encoding or I/O fails.
  - `CollectionNotFoundError`: If the collection does not exist (auto-created).

**Example**:

    ids = db.insert_many("users", [{"name": "Bob"}, {"name": "Charlie"}])

#### `find(collection: str, query: Dict = None, limit: int = None, skip: int = 0, sort: Dict = None) -> List[Dict]`

Queries records matching the specified criteria, leveraging indexes when possible.

- **Parameters**:
  - `collection`: Name of the collection.
  - `query`: Optional dictionary with query conditions (e.g., `{"name": "Alice"}`).
  - `limit`: Optional maximum number of records to return.
  - `skip`: Number of records to skip (for pagination).
  - `sort`: Optional dictionary for sorting (e.g., `{"age": 1}` for ascending, `{"age": -1}` for descending).
- **Returns**: List of matching records.
- **Raises**:
  - `CollectionNotFoundError`: If the collection does not exist.

**Example**:

    results = db.find("users", {"age": {"$gt": 20}}, limit=10, sort={"age": 1})

#### `update(collection: str, record_id: str, update_data: Dict) -> bool`

Updates a record by its `_id`.

- **Parameters**:
  - `collection`: Name of the collection.
  - `record_id`: ID of the record to update.
  - `update_data`: Dictionary with fields to update.
- **Returns**: `True` if updated, `False` if not found.
- **Raises**:
  - `CollectionNotFoundError`: If the collection does not exist.
  - `FluxDBError`: If I/O fails.

**Example**:

    db.update("users", user_id, {"status": "inactive"})

#### `delete(collection: str, record_id: str) -> bool`

Deletes a record by its `_id`.

- **Parameters**:
  - `collection`: Name of the collection.
  - `record_id`: ID of the record to delete.
- **Returns**: `True` if deleted, `False` if not found.
- **Raises**:
  - `CollectionNotFoundError`: If the collection does not exist.
  - `FluxDBError`: If I/O fails.

**Example**:

    db.delete("users", user_id)

#### `exists(collection: str, record_id: str) -> bool`

Checks if a record exists by its `_id`.

- **Parameters**:
  - `collection`: Name of the collection.
  - `record_id`: ID of the record to check.
- **Returns**: `True` if the record exists, `False` otherwise.
- **Raises**: None.

**Example**:

    if db.exists("users", user_id):
        print("User exists!")

#### `count(collection: str, query: Dict = None) -> int`

Counts records matching the query.

- **Parameters**:
  - `collection`: Name of the collection.
  - `query`: Optional query dictionary.
- **Returns**: Number of matching records.
- **Raises**: None.

**Example**:

    count = db.count("users", {"status": "active"})

### Transactions

#### `begin_transaction() -> None`

Starts a new transaction for atomic operations.

- **Parameters**: None.
- **Returns**: None.
- **Raises**:
  - `TransactionError`: If a transaction is already active.

**Example**:

    db.begin_transaction()

#### `commit() -> None`

Commits the active transaction, flushing buffered writes to disk.

- **Parameters**: None.
- **Returns**: None.
- **Raises**:
  - `TransactionError`: If no transaction is active or commit fails.

**Example**:

    db.commit()

#### `rollback() -> None`

Rolls back the active transaction, discarding buffered operations.

- **Parameters**: None.
- **Returns**: None.
- **Raises**:
  - `TransactionError`: If no transaction is active.

**Example**:

    db.rollback()

**Transaction Example**:

    db.begin_transaction()
    try:
        db.insert("users", {"name": "Eve"})
        db.insert("users", {"name": "Frank"})
        db.commit()
    except Exception:
        db.rollback()

### Aggregation

#### `aggregate(collection: str, pipeline: List[Dict]) -> List[Dict]`

Performs aggregation on a collection, supporting `$group` with `$sum` and `$count`.

- **Parameters**:
  - `collection`: Name of the collection.
  - `pipeline`: List of aggregation stages (e.g., `[{"$group": {"_id": "$category", "total": {"$sum": 1}}}]`).
- **Returns**: List of aggregated results.
- **Raises**: None.

**Example**:

    results = db.aggregate("products", [
        {"$group": {"_id": "$category", "count": {"$count": 1}}}
    ])

### Import/Export

#### `export_collection(collection: str, output_file: str) -> bool`

Exports a collection to a binary file.

- **Parameters**:
  - `collection`: Name of the collection.
  - `output_file`: Path to the output file (e.g., `backup.fdb`).
- **Returns**: `True` if exported, `False` if not found.
- **Raises**:
  - `FluxDBError`: If export fails due to I/O issues.

**Example**:

    db.export_collection("users", "users_backup.fdb")

#### `import_collection(collection: str, input_file: str) -> bool`

Imports a collection from a binary file, rebuilding indexes.

- **Parameters**:
  - `collection`: Name of the collection.
  - `input_file`: Path to the input file.
- **Returns**: `True` if imported, `False` if file not found.
- **Raises**:
  - `FluxDBError`: If import fails due to I/O issues.

**Example**:

    db.import_collection("users", "users_backup.fdb")

## Query Language

FluxDB supports a dictionary-based query language for filtering records.

### Supported Operators

| Operator       | Syntax                              | Description                     |
|----------------|-------------------------------------|---------------------------------|
| Exact Match    | `{"field": "value"}`               | Matches exact field value       |
| Greater Than   | `{"field": {"$gt": value}}`        | Matches values greater than     |
| Less Than      | `{"field": {"$lt": value}}`        | Matches values less than        |
| In List        | `{"field": {"$in": [v1, v2]}}`    | Matches values in a list        |

### Examples

**Exact Match**:

    db.find("users", {"name": "Alice"})

**Comparison**:

    db.find("users", {"age": {"$gt": 20, "$lt": 30}})

**In List**:

    db.find("users", {"status": {"$in": ["active", "pending"]}})

**Combined Query**:

    db.find("users", {
        "age": {"$gt": 20, "$lt": 30},
        "status": {"$in": ["active"]}
    }, sort={"age": 1}, limit=10)

## Roadmap

- Add CLI tool for database inspection and management.
- Support data file compression to reduce disk usage.
- Implement nested and relational-style queries for advanced use cases.

## License

MIT License. See [LICENSE](https://github.com/lkardas/fluxdb/tree/main?tab=MIT-1-ov-file#) for details.

**Navigation**: [Features](#features) | [Installation](#installation) | [Quick Start](#quick-start) | [API](#api) | [Query Language](#query-language) | [Roadmap](#roadmap)
