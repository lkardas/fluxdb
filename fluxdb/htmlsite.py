# HTML templates and CSS as strings for FluxDB admin panel

INDEX_HTML = """
<html>
    <head>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="/static/css/style.css" rel="stylesheet">
        <script src="https://kit.fontawesome.com/a076d05399.js"></script>
    </head>
    <body class="bg-light">
        <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
            <div class="container-fluid">
                <a class="navbar-brand" href="{{ url_for('fluxdbadminview.index') }}">FluxDB Admin</a>
                <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                    <span class="navbar-toggler-icon"></span>
                </button>
                <div class="collapse navbar-collapse" id="navbarNav">
                    <ul class="navbar-nav ms-auto">
                        <li class="nav-item">
                            <a class="nav-link" href="{{ url_for('logout') }}">Logout</a>
                        </li>
                    </ul>
                </div>
            </div>
        </nav>
        <div class="container mt-4">
            <h1 class="mb-4">FluxDB Collections</h1>
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                            {{ message }}
                            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                        </div>
                    {% endfor %}
                {% endif %}
            {% endwith %}
            <div class="card mb-4">
                <div class="card-body">
                    <h5 class="card-title">Create New Collection</h5>
                    <form method="post" action="{{ url_for('fluxdbadminview.create_collection') }}">
                        <div class="mb-3">
                            <label for="name" class="form-label">Collection Name</label>
                            <input type="text" name="name" id="name" class="form-control" placeholder="e.g., users" required>
                        </div>
                        <button type="submit" class="btn btn-primary"><i class="fas fa-plus me-2"></i>Create</button>
                    </form>
                </div>
            </div>
            {% if collections %}
                <div class="list-group">
                    {% for collection in collections %}
                        <div class="list-group-item d-flex justify-content-between align-items-center">
                            <a href="{{ url_for('fluxdbadminview.collection', name=collection) }}" class="text-decoration-none">
                                <i class="fas fa-database me-2"></i>{{ collection }}
                            </a>
                            <a href="{{ url_for('fluxdbadminview.drop_collection', name=collection) }}" class="btn btn-sm btn-danger" onclick="return confirm('Are you sure you want to delete collection {{ collection }}?')">
                                <i class="fas fa-trash"></i> Delete
                            </a>
                        </div>
                    {% endfor %}
                </div>
            {% else %}
                <p class="text-muted">No collections found.</p>
            {% endif %}
        </div>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
</html>
"""

COLLECTION_HTML = """
<html>
    <head>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="/static/css/style.css" rel="stylesheet">
        <script src="https://kit.fontawesome.com/a076d05399.js"></script>
    </head>
    <body class="bg-light">
        <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
            <div class="container-fluid">
                <a class="navbar-brand" href="{{ url_for('fluxdbadminview.index') }}">FluxDB Admin</a>
                <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                    <span class="navbar-toggler-icon"></span>
                </button>
                <div class="collapse navbar-collapse" id="navbarNav">
                    <ul class="navbar-nav ms-auto">
                        <li class="nav-item">
                            <a class="nav-link" href="{{ url_for('logout') }}">Logout</a>
                        </li>
                    </ul>
                </div>
            </div>
        </nav>
        <div class="container mt-4">
            <h1 class="mb-4">Collection: {{ collection }}</h1>
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                            {{ message }}
                            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                        </div>
                    {% endfor %}
                {% endif %}
            {% endwith %}
            <div class="card mb-4">
                <div class="card-body">
                    <h5 class="card-title">Add New Record</h5>
                    <form method="post">
                        <div class="mb-3">
                            <label for="data" class="form-label">Record (JSON format, e.g., {"name": "value"})</label>
                            <textarea name="data" id="data" class="form-control" rows="4" placeholder='{"name": "value"}' required></textarea>
                        </div>
                        <button type="submit" class="btn btn-primary"><i class="fas fa-plus me-2"></i>Add Record</button>
                    </form>
                </div>
            </div>
            <h3>Records</h3>
            {% if records %}
                <div class="table-responsive">
                    <table class="table table-striped table-hover">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Data</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for record in records %}
                                <tr>
                                    <td>{{ record['_id'] }}</td>
                                    <td><pre>{{ record | tojson(indent=2) }}</pre></td>
                                    <td>
                                        <a href="{{ url_for('fluxdbadminview.edit', name=collection, record_id=record['_id']) }}" class="btn btn-sm btn-warning me-2">
                                            <i class="fas fa-edit"></i> Edit
                                        </a>
                                        <a href="{{ url_for('fluxdbadminview.delete', name=collection, record_id=record['_id']) }}" class="btn btn-sm btn-danger" onclick="return confirm('Are you sure you want to delete this record?')">
                                            <i class="fas fa-trash"></i> Delete
                                        </a>
                                    </td>
                                </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            {% else %}
                <p class="text-muted">No records found.</p>
            {% endif %}
        </div>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
</html>
"""

EDIT_HTML = """
<html>
    <head>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="/static/css/style.css" rel="stylesheet">
        <script src="https://kit.fontawesome.com/a076d05399.js"></script>
    </head>
    <body class="bg-light">
        <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
            <div class="container-fluid">
                <a class="navbar-brand" href="{{ url_for('fluxdbadminview.index') }}">FluxDB Admin</a>
                <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                    <span class="navbar-toggler-icon"></span>
                </button>
                <div class="collapse navbar-collapse" id="navbarNav">
                    <ul class="navbar-nav ms-auto">
                        <li class="nav-item">
                            <a class="nav-link" href="{{ url_for('logout') }}">Logout</a>
                        </li>
                    </ul>
                </div>
            </div>
        </nav>
        <div class="container mt-4">
            <h1 class="mb-4">Edit Record in {{ collection }}</h1>
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                            {{ message }}
                            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                        </div>
                    {% endfor %}
                {% endif %}
            {% endwith %}
            <div class="card">
                <div class="card-body">
                    <h5 class="card-title">Record ID: {{ record_id }}</h5>
                    <form method="post">
                        <div class="mb-3">
                            <label for="data" class="form-label">Record (JSON format, e.g., {"name": "value"})</label>
                            <textarea name="data" id="data" class="form-control" rows="6" required>{{ record | tojson(indent=2) }}</textarea>
                        </div>
                        <button type="submit" class="btn btn-primary"><i class="fas fa-save me-2"></i>Save Changes</button>
                        <a href="{{ url_for('fluxdbadminview.collection', name=collection) }}" class="btn btn-secondary">Cancel</a>
                    </form>
                </div>
            </div>
        </div>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
</html>
"""

STYLE_CSS = """
body {
    background-color: #f8f9fa;
}

.card {
    transition: transform 0.2s;
}

.card:hover {
    transform: translateY(-5px);
}

.list-group-item {
    transition: background-color 0.2s;
}

.list-group-item:hover {
    background-color: #e9ecef;
}

.btn {
    transition: all 0.2s;
}

.alert {
    animation: fadeIn 0.5s;
}

@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

.navbar {
    margin-bottom: 20px;
}
"""
