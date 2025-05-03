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
- **Dependencies**: Requires `psutil` for memory management, `flask` for the web server, and `flask-admin` for the administrative interface.
- **Web Interface**: Flask-based web server for browsing and managing collections via a browser.
- **Bulk Operations**: Optimized bulk insert, update, and delete for large datasets.
- **Schema Validation**: Optional schema enforcement for collections to ensure data consistency.
- **Event Hooks**: Pre- and post-operation hooks for custom logic (e.g., logging, validation).
- **Concurrent Access**: Thread-safe operations for multi-threaded applications.
- **Query Optimization**: Index-aware query planner for improved performance on complex queries.

## Installation

FluxDB is not yet available on PyPI. Install from TestPyPI:

    pip install -i https://test.pypi.org/simple/ fluxdb

**Requirements**:
- Python 3.9 or higher

Import in your project:

    from fluxdb import FluxDB

## Quick Start

Get started with FluxDB in a few lines of code:

    from fluxdb import FluxDB

    # Initialize database in the "data" directory
    db = FluxDB("data")

    # Create a collection with indexed fields and schema
    db.create_collection("users", indexed_fields=["age", "status"], schema={"name": str, "age": int, "status": str})

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

    # Start web interface
    db.start_web_interface(port=5000)

## API

**Navigation**: [Initialization](#initialization) | [Collection Management](#collection-management) | [Data Operations](#data-operations) | [Transactions](#transactions) | [Aggregation](#aggregation) | [Import/Export](#importexport) | [Web Interface](#web-interface) | [Event Hooks](#event-hooks)

### Initialization

#### `FluxDB(db_path: str, storage_backend: StorageBackend = None, thread_safe: bool = True)`

Initializes a new FluxDB instance.

- **Parameters**:
  - `db_path`: Directory for storing `.fdb` files and indexes.
  - `storage_backend`: Optional custom storage backend (defaults to `BinaryStorage`).
  - `thread_safe`: Enable thread-safe operations (default: `True`).
- **Returns**: A `FluxDB` instance.
- **Raises**: None.

**Example**:

    db = FluxDB("data", thread_safe=True)

### Collection Management

#### `create_collection(collection: str, indexed_fields: List[str] = None, schema: Dict = None) -> bool`

Creates a new collection, optionally with indexed fields and schema.

- **Parameters**:
  - `collection`: Name of the collection.
  - `indexed_fields`: List of fields to index (e.g., `["age", "status"]`).
  - `schema`: Optional dictionary specifying field types (e.g., `{"name": str, "age": int}`).
- **Returns**: `True` if created, `False` if the collection exists.
- **Raises**:
  - `FluxDBError`: If creation fails due to I/O issues or invalid schema.

**Example**:

    db.create_collection("users", indexed_fields=["age", "status"], schema={"name": str, "age": int})

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
  - `FluxDBError`: If encoding, I/O, or schema validation fails.
  - `CollectionNotFoundError`: If the collection does not exist (auto-created).

**Example**:

    user_id = db.insert("users", {"name": "Alice", "age": 30, "status": "active"})

#### `insert_many(collection: str, data_list: List[Dict]) -> List[str]`

Inserts multiple records in a single operation.

- **Parameters**:
  - `collection`: Name of the collection.
  - `data_list`: List of dictionaries containing record data.
- **Returns**: List of `_id`s for the inserted records.
- **Raises**:
  - `FluxDBError`: If encoding, I/O, or schema validation fails.
  - `CollectionNotFoundError`: If the collection does not exist (auto-created).

**Example**:

    ids = db.insert_many("users", [{"name": "Bob"}, {"name": "Charlie"}])

#### `find(collection: str, query: Dict = None, limit: int = None, skip: int = 0, sort: Dict = None, optimize: bool = True) -> List[Dict]`

Queries records matching the specified criteria, leveraging indexes when possible.

- **Parameters**:
  - `collection`: Name of the collection.
  - `query`: Optional dictionary with query conditions (e.g., `{"name": "Alice"}`).
  - `limit`: Optional maximum number of records to return.
  - `skip`: Number of records to skip (for pagination).
  - `sort`: Optional dictionary for sorting (e.g., `{"age": 1}` for ascending, `{"age": -1}` for descending).
  - `optimize`: Use query planner for index optimization (default: `True`).
- **Returns**: List of matching records.
- **Raises**:
  - `CollectionNotFoundError`: If the collection does not exist.

**Example**:

    results = db.find("users", {"age": {"$gt": 20}}, limit=10, sort={"age": 1}, optimize=True)

#### `update(collection: str, record_id: str, update_data: Dict) -> bool`

Updates a record by its `_id`.

- **Parameters**:
  - `collection`: Name of the collection.
  - `record_id`: ID of the record to update.
  - `update_data`: Dictionary with fields to update.
- **Returns**: `True` if updated, `False` if not found.
- **Raises**:
  - `CollectionNotFoundError`: If the collection does not exist.
  - `FluxDBError`: If I/O or schema validation fails.

**Example**:

    db.update("users", user_id, {"status": "inactive"})

#### `update_many(collection: str, query: Dict, update_data: Dict) -> int`

Updates multiple records matching the query.

- **Parameters**:
  - `collection`: Name of the collection.
  - `query`: Query to select records to update.
  - `update_data`: Dictionary with fields to update.
- **Returns**: Number of updated records.
- **Raises**:
  - `CollectionNotFoundError`: If the collection does not exist.
  - `FluxDBError`: If I/O or schema validation fails.

**Example**:

    count = db.update_many("users", {"status": "active"}, {"status": "inactive"})

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

#### `delete_many(collection: str, query: Dict) -> int`

Deletes multiple records matching the query.

- **Parameters**:
  - `collection`: Name of the collection.
  - `query`: Query to select records to delete.
- **Returns**: Number of deleted records.
- **Raises**:
  - `CollectionNotFoundError`: If the collection does not exist.
  - `FluxDBError`: If I/O fails.

**Example**:

    count = db.delete_many("users", {"status": "inactive"})

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

Performs aggregation on a collection, supporting `$group` with `$sum`, `$count`, `$avg`, `$min`, and `$max`.

- **Parameters**:
  - `collection`: Name of the collection.
  - `pipeline`: List of aggregation stages (e.g., `[{"$group": {"_id": "$category", "total": {"$sum": 1}}}]`).
- **Returns**: List of aggregated results.
- **Raises**: None.

**Example**:

    results = db.aggregate("products", [
        {"$group": {"_id": "$category", "avg_price": {"$avg": "$price"}}}
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

### Web Interface

#### `start_web_interface(host: str = "127.0.0.1", port: int = 5000) -> None`

Starts a Flask-based web server for browsing and managing collections.

- **Parameters**:
  - `host`: Host address (default: `"127.0.0.1"`).
  - `port`: Port number (default: `5000`).
- **Returns**: None.
- **Raises**:
  - `FluxDBError`: If the server fails to start.

**Example**:

    db.start_web_interface(port=5000)

### Event Hooks

#### `register_hook(collection: str, operation: str, callback: Callable) -> None`

Registers a callback for pre- or post-operation events (e.g., `pre_insert`, `post_update`).

- **Parameters**:
  - `collection`: Name of the collection.
  - `operation`: Event type (e.g., `pre_insert`, `post_update`).
  - `callback`: Function to call with record data.
- **Returns**: None.
- **Raises**: None.

**Example**:

    def log_insert(data):
        print(f"Inserting: {data}")

    db.register_hook("users", "pre_insert", log_insert)

## Query Language

FluxDB supports a dictionary-based query language for filtering records.

### Supported Operators

| Operator       | Syntax                              | Description                     |
|----------------|-------------------------------------|---------------------------------|
| Exact Match    | `{"field": "value"}`               | Matches exact field value       |
| Greater Than   | `{"field": {"$gt": value}}`        | Matches values greater than     |
| Less Than      | `{"field": {"$lt": value}}`        | Matches values less than        |
| In List        | `{"field": {"$in": [v1, v2]}}`    | Matches values in a list        |
| Greater or Equal | `{"field": {"$gte": value}}`     | Matches values greater or equal |
| Less or Equal  | `{"field": {"$lte": value}}`      | Matches values less or equal    |
| Not Equal      | `{"field": {"$ne": value}}`       | Matches values not equal        |

### Examples

**Exact Match**:

    db.find("users", {"name": "Alice"})

**Comparison**:

    db.find("users", {"age": {"$gte": 20, "$lte": 30}})

**In List**:

    db.find("users", {"status": {"$in": ["active", "pending"]}})

**Not Equal**:

    db.find("users", {"status": {"$ne": "inactive"}})

**Combined Query**:

    db.find("users", {
        "age": {"$gte": 20, "$lte": 30},
        "status": {"$in": ["active"]}
    }, sort={"age": 1}, limit=10)

## Roadmap

- Add CLI tool for database inspection and management.
- Support data file compression to reduce disk usage.
- Implement nested and relational-style queries for advanced use cases.
- Add support for full-text search indexing.
- Introduce replication for distributed setups.
- Enhance web interface with query builder and visualization tools.

## License

MIT License. See [LICENSE](https://github.com/lkardas/fluxdb/tree/main?tab=MIT-1-ov-file#) for details.

**Navigation**: [Features](#features) | [Installation](#installation) | [Quick Start](#quick-start) | [API](#api) | [Query Language](#query-language) | [Roadmap](#roadmap)
