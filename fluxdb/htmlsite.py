# HTML templates and CSS for FluxDB admin panel

INDEX_HTML = """
<html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=1200">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="/static/css/style.css" rel="stylesheet">
        <script src="https://kit.fontawesome.com/a076d05399.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/ace-builds@1.32.9/src-min-noconflict/ace.js"></script>
        <script>
            function showCookieConsent() {
                if (!{{ cookie_consent|tojson }}) {
                    document.getElementById('cookieConsentModal').style.display = 'block';
                }
            }
            window.onload = showCookieConsent;
        </script>
    </head>
    <body class="{{ 'bg-light' if theme == 'light' else 'bg-dark text-light' }}">
        <nav class="navbar navbar-expand-lg {{ 'navbar-light bg-primary' if theme == 'light' else 'navbar-dark bg-dark' }}">
            <div class="container" style="max-width: 1200px;">
                <a class="navbar-brand" href="{{ url_for('fluxdbadminview.index') }}">FluxDB Admin</a>
                <div class="navbar-nav ms-auto">
                    <form method="post" action="{{ url_for('set_theme') }}" class="d-inline">
                        <select name="theme" onchange="this.form.submit()" class="form-select form-select-sm">
                            <option value="light" {{ 'selected' if theme == 'light' }}>Light</option>
                            <option value="dark" {{ 'selected' if theme == 'dark' }}>Dark</option>
                        </select>
                    </form>
                    <a class="nav-link" href="{{ url_for('logout') }}">Logout</a>
                </div>
            </div>
        </nav>
        <div class="container mt-4" style="max-width: 1200px;">
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
                    <h5 class="card-title">Database Statistics</h5>
                    <p>Collections: {{ stats.collections }}</p>
                    <p>Total Records: {{ stats.total_records }}</p>
                    <p>Database Size: {{ stats.db_size }} bytes</p>
                </div>
            </div>
            <div class="card mb-4">
                <div class="card-body">
                    <h5 class="card-title">Create New Collection</h5>
                    <form method="post" action="{{ url_for('fluxdbadminview.create_collection') }}">
                        <div class="mb-3">
                            <label for="name" class="form-label">Collection Name</label>
                            <input type="text" name="name" id="name" class="form-control" placeholder="e.g., users" required>
                        </div>
                        <div class="mb-3">
                            <label for="indexed_fields" class="form-label">Indexed Fields (comma-separated)</label>
                            <input type="text" name="indexed_fields" id="indexed_fields" class="form-control" placeholder="e.g., name,age">
                        </div>
                        <button type="submit" class="btn btn-primary"><i class="fas fa-plus me-2"></i>Create</button>
                    </form>
                </div>
            </div>
            {% if collections %}
                <div class="list-group">
                    {% for collection in collections %}
                        <div class="list-group-item d-flex justify-content-between align-items-center">
                            <a href="{{ url_for('fluxdbadminview.collection', collection_name=collection) }}" class="text-decoration-none">
                                <i class="fas fa-database me-2"></i>{{ collection }}
                            </a>
                            <a href="{{ url_for('fluxdbadminview.drop_collection', collection_name=collection) }}" class="btn btn-sm btn-danger" onclick="return confirm('Are you sure you want to delete collection {{ collection }}?')">
                                <i class="fas fa-trash"></i> Delete
                            </a>
                        </div>
                    {% endfor %}
                </div>
            {% else %}
                <p class="text-muted">No collections found.</p>
            {% endif %}
        </div>
        {{ COOKIE_CONSENT_HTML | safe }}
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
</html>
"""

COLLECTION_HTML = """
<html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=1200">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="/static/css/style.css" rel="stylesheet">
        <script src="https://kit.fontawesome.com/a076d05399.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/ace-builds@1.32.9/src-min-noconflict/ace.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/ace-builds@1.32.9/src-min-noconflict/mode-json.js"></script>
        <script>
            function showCookieConsent() {
                if (!{{ cookie_consent|tojson }}) {
                    document.getElementById('cookieConsentModal').style.display = 'block';
                }
            }
            window.onload = function() {
                showCookieConsent();
                var editor = ace.edit("data-editor");
                editor.setTheme("ace/theme/{{ 'chrome' if theme == 'light' else 'monokai' }}");
                editor.session.setMode("ace/mode/json");
                editor.setOptions({ maxLines: 20, minLines: 10 });
                var updateEditor = ace.edit("update-editor");
                updateEditor.setTheme("ace/theme/{{ 'chrome' if theme == 'light' else 'monokai' }}");
                updateEditor.session.setMode("ace/mode/json");
                updateEditor.setOptions({ maxLines: 20, minLines: 10 });
            };
            function allowDrop(ev) {
                ev.preventDefault();
            }
            function drop(ev) {
                ev.preventDefault();
                var file = ev.dataTransfer.files[0];
                document.getElementById('bulk-file').files = ev.dataTransfer.files;
                document.getElementById('bulk-file-label').innerText = file.name;
            }
        </script>
    </head>
    <body class="{{ 'bg-light' if theme == 'light' else 'bg-dark text-light' }}">
        <nav class="navbar navbar-expand-lg {{ 'navbar-light bg-primary' if theme == 'light' else 'navbar-dark bg-dark' }}">
            <div class="container" style="max-width: 1200px;">
                <a class="navbar-brand" href="{{ url_for('fluxdbadminview.index') }}">FluxDB Admin</a>
                <div class="navbar-nav ms-auto">
                    <form method="post" action="{{ url_for('set_theme') }}" class="d-inline">
                        <select name="theme" onchange="this.form.submit()" class="form-select form-select-sm">
                            <option value="light" {{ 'selected' if theme == 'light' }}>Light</option>
                            <option value="dark" {{ 'selected' if theme == 'dark' }}>Dark</option>
                        </select>
                    </form>
                    <a class="nav-link" href="{{ url_for('logout') }}">Logout</a>
                </div>
            </div>
        </nav>
        <div class="container mt-4" style="max-width: 1200px;">
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
                    <h5 class="card-title">Collection Actions</h5>
                    <a href="{{ url_for('fluxdbadminview.indexes', collection_name=collection) }}" class="btn btn-primary mb-2"><i class="fas fa-index me-2"></i>Manage Indexes</a>
                    <a href="{{ url_for('fluxdbadminview.aggregate', collection_name=collection) }}" class="btn btn-primary mb-2"><i class="fas fa-chart-bar me-2"></i>Aggregate</a>
                    <form method="post" action="{{ url_for('fluxdbadminview.transaction', collection_name=collection) }}" class="d-inline">
                        <input type="hidden" name="action" value="begin">
                        <button type="submit" class="btn btn-primary mb-2"><i class="fas fa-play me-2"></i>Begin Transaction</button>
                    </form>
                    <form method="post" action="{{ url_for('fluxdbadminview.transaction', collection_name=collection) }}" class="d-inline">
                        <input type="hidden" name="action" value="commit">
                        <button type="submit" class="btn btn-success mb-2"><i class="fas fa-check me-2"></i>Commit</button>
                    </form>
                    <form method="post" action="{{ url_for('fluxdbadminview.transaction', collection_name=collection) }}" class="d-inline">
                        <input type="hidden" name="action" value="rollback">
                        <button type="submit" class="btn btn-danger mb-2"><i class="fas fa-undo me-2"></i>Rollback</button>
                    </form>
                </div>
            </div>
            <div class="card mb-4">
                <div class="card-body">
                    <h5 class="card-title">Add New Record</h5>
                    <form method="post">
                        <input type="hidden" name="action" value="insert">
                        <div class="mb-3">
                            <label for="data-editor" class="form-label">Record (JSON format)</label>
                            <div id="data-editor" style="height: 200px;">{}</div>
                            <textarea name="data" id="data" class="d-none"></textarea>
                        </div>
                        <button type="submit" class="btn btn-primary" onclick="document.getElementById('data').value = ace.edit('data-editor').getValue();"><i class="fas fa-plus me-2"></i>Add Record</button>
                    </form>
                </div>
            </div>
            <div class="card mb-4">
                <div class="card-body">
                    <h5 class="card-title">Bulk Insert (JSON or CSV)</h5>
                    <form method="post" enctype="multipart/form-data">
                        <input type="hidden" name="action" value="bulk_insert">
                        <div class="mb-3" ondrop="drop(event)" ondragover="allowDrop(event)" style="border: 2px dashed #ced4da; padding: 20px;">
                            <label for="bulk-file" class="form-label" id="bulk-file-label">Drag and drop JSON or CSV file here</label>
                            <input type="file" name="file" id="bulk-file" accept=".json,.csv" class="form-control" onchange="document.getElementById('bulk-file-label').innerText = this.files[0].name;">
                        </div>
                        <button type="submit" class="btn btn-primary"><i class="fas fa-upload me-2"></i>Upload and Insert</button>
                    </form>
                </div>
            </div>
            <div class="card mb-4">
                <div class="card-body">
                    <h5 class="card-title">Search Records</h5>
                    <form method="get">
                        <div class="mb-3">
                            <label for="query" class="form-label">Query (JSON format, e.g., {"name": "value"})</label>
                            <textarea name="query" id="query" class="form-control" rows="4">{{ query | tojson(indent=2) }}</textarea>
                        </div>
                        <div class="mb-3">
                            <label for="per_page" class="form-label">Records per page</label>
                            <select name="per_page" id="per_page" class="form-select" onchange="this.form.submit()">
                                <option value="10" {{ 'selected' if per_page == 10 }}>10</option>
                                <option value="25" {{ 'selected' if per_page == 25 }}>25</option>
                                <option value="50" {{ 'selected' if per_page == 50 }}>50</option>
                            </select>
                        </div>
                        <button type="submit" class="btn btn-primary"><i class="fas fa-search me-2"></i>Search</button>
                    </form>
                </div>
            </div>
            <div class="card mb-4">
                <div class="card-body">
                    <h5 class="card-title">Import/Export</h5>
                    <form method="post" action="{{ url_for('fluxdbadminview.import_collection', collection_name=collection) }}" enctype="multipart/form-data" class="d-inline">
                        <input type="file" name="file" accept=".fdb" class="form-control d-inline-block w-auto">
                        <button type="submit" class="btn btn-primary"><i class="fas fa-upload me-2"></i>Import</button>
                    </form>
                    <a href="{{ url_for('fluxdbadminview.export', collection_name=collection) }}" class="btn btn-primary"><i class="fas fa-download me-2"></i>Export</a>
                </div>
            </div>
            <div class="card mb-4">
                <div class="card-body">
                    <h5 class="card-title">Indexes</h5>
                    {% if indexes %}
                        <ul>
                            {% for index in indexes %}
                                <li>{{ index }}</li>
                            {% endfor %}
                        </ul>
                    {% else %}
                        <p class="text-muted">No indexes.</p>
                    {% endif %}
                </div>
            </div>
            <h3>Records</h3>
            {% if records %}
                <form method="post">
                    <input type="hidden" name="action" value="bulk_delete">
                    <div class="mb-3">
                        <button type="submit" class="btn btn-danger" onclick="return confirm('Are you sure you want to delete selected records?')"><i class="fas fa-trash me-2"></i>Delete Selected</button>
                    </div>
                    <div class="card mb-4">
                        <div class="card-body">
                            <h5 class="card-title">Bulk Update</h5>
                            <div class="mb-3">
                                <label for="update-editor" class="form-label">Update Data (JSON format)</label>
                                <div id="update-editor" style="height: 200px;">{}</div>
                                <textarea name="update_data" id="update-data" class="d-none"></textarea>
                            </div>
                            <button type="submit" class="btn btn-primary" onclick="document.getElementById('update-data').value = ace.edit('update-editor').getValue(); document.querySelector('input[name=action]').value = 'bulk_update';"><i class="fas fa-edit me-2"></i>Update Selected</button>
                        </div>
                    </div>
                    <div class="table-responsive">
                        <table class="table table-striped table-hover">
                            <thead>
                                <tr>
                                    <th><input type="checkbox" onclick="document.querySelectorAll('input[name=record_ids]').forEach(cb => cb.checked = this.checked)"></th>
                                    <th><a href="?sort=_id&sort_dir={{ -sort_dir if sort_field == '_id' else 1 }}">ID {{ '↑' if sort_field == '_id' and sort_dir == 1 else '↓' if sort_field == '_id' else '' }}</a></th>
                                    {% for field in fields %}
                                        <th><a href="?sort={{ field }}&sort_dir={{ -sort_dir if sort_field == field else 1 }}">{{ field }} {{ '↑' if sort_field == field and sort_dir == 1 else '↓' if sort_field == field else '' }}</a></th>
                                    {% endfor %}
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for record in records %}
                                    <tr>
                                        <td><input type="checkbox" name="record_ids" value="{{ record['_id'] }}"></td>
                                        <td>{{ record['_id'] }}</td>
                                        {% for field in fields %}
                                            <td>{{ record.get(field, '') }}</td>
                                        {% endfor %}
                                        <td>
                                            <a href="{{ url_for('fluxdbadminview.edit', collection_name=collection, record_id=record['_id']) }}" class="btn btn-sm btn-warning me-2"><i class="fas fa-edit"></i> Edit</a>
                                            <a href="{{ url_for('fluxdbadminview.delete', collection_name=collection, record_id=record['_id']) }}" class="btn btn-sm btn-danger" onclick="return confirm('Are you sure you want to delete this record?')"><i class="fas fa-trash"></i> Delete</a>
                                        </td>
                                    </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                </form>
                <nav>
                    <ul class="pagination">
                        {% if page > 1 %}
                            <li class="page-item"><a class="page-link" href="?page={{ page - 1 }}&per_page={{ per_page }}&sort={{ sort_field }}&sort_dir={{ sort_dir }}&query={{ query | tojson | urlencode }}">Previous</a></li>
                        {% endif %}
                        {% for p in range(1, total_pages + 1) %}
                            <li class="page-item {{ 'active' if p == page }}"><a class="page-link" href="?page={{ p }}&per_page={{ per_page }}&sort={{ sort_field }}&sort_dir={{ sort_dir }}&query={{ query | tojson | urlencode }}">{{ p }}</a></li>
                        {% endfor %}
                        {% if page < total_pages %}
                            <li class="page-item"><a class="page-link" href="?page={{ page + 1 }}&per_page={{ per_page }}&sort={{ sort_field }}&sort_dir={{ sort_dir }}&query={{ query | tojson | urlencode }}">Next</a></li>
                        {% endif %}
                    </ul>
                </nav>
            {% else %}
                <p class="text-muted">No records found.</p>
            {% endif %}
        </div>
        {{ COOKIE_CONSENT_HTML | safe }}
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
</html>
"""

EDIT_HTML = """
<html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=1200">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="/static/css/style.css" rel="stylesheet">
        <script src="https://kit.fontawesome.com/a076d05399.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/ace-builds@1.32.9/src-min-noconflict/ace.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/ace-builds@1.32.9/src-min-noconflict/mode-json.js"></script>
        <script>
            function showCookieConsent() {
                if (!{{ cookie_consent|tojson }}) {
                    document.getElementById('cookieConsentModal').style.display = 'block';
                }
            }
            window.onload = function() {
                showCookieConsent();
                var editor = ace.edit("data-editor");
                editor.setTheme("ace/theme/{{ 'chrome' if theme == 'light' else 'monokai' }}");
                editor.session.setMode("ace/mode/json");
                editor.setOptions({ maxLines: 20, minLines: 10 });
                editor.setValue(JSON.stringify({{ record | tojson }}, null, 2));
                document.getElementById('dynamic-form').addEventListener('input', updateJson);
            };
            function updateJson() {
                var data = {};
                document.querySelectorAll('#dynamic-form input').forEach(input => {
                    data[input.name] = input.value;
                });
                try {
                    document.getElementById('data').value = JSON.stringify(data, null, 2);
                    ace.edit('data-editor').setValue(JSON.stringify(data, null, 2));
                } catch (e) {
                    console.error('Invalid data');
                }
            }
            function previewChanges() {
                try {
                    var data = JSON.parse(ace.edit('data-editor').getValue());
                    document.getElementById('preview').innerText = JSON.stringify(data, null, 2);
                } catch (e) {
                    document.getElementById('preview').innerText = 'Invalid JSON';
                }
            }
        </script>
    </head>
    <body class="{{ 'bg-light' if theme == 'light' else 'bg-dark text-light' }}">
        <nav class="navbar navbar-expand-lg {{ 'navbar-light bg-primary' if theme == 'light' else 'navbar-dark bg-dark' }}">
            <div class="container" style="max-width: 1200px;">
                <a class="navbar-brand" href="{{ url_for('fluxdbadminview.index') }}">FluxDB Admin</a>
                <div class="navbar-nav ms-auto">
                    <form method="post" action="{{ url_for('set_theme') }}" class="d-inline">
                        <select name="theme" onchange="this.form.submit()" class="form-select form-select-sm">
                            <option value="light" {{ 'selected' if theme == 'light' }}>Light</option>
                            <option value="dark" {{ 'selected' if theme == 'dark' }}>Dark</option>
                        </select>
                    </form>
                    <a class="nav-link" href="{{ url_for('logout') }}">Logout</a>
                </div>
            </div>
        </nav>
        <div class="container mt-4" style="max-width: 1200px;">
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
                    <form method="post" id="dynamic-form">
                        <div class="row">
                            <div class="col-md-6">
                                <h6>Dynamic Form</h6>
                                {% for field in fields %}
                                    {% if field != '_id' %}
                                        <div class="mb-3">
                                            <label for="{{ field }}" class="form-label">{{ field }}</label>
                                            <input type="text" name="{{ field }}" id="{{ field }}" class="form-control" value="{{ record.get(field, '') }}">
                                        </div>
                                    {% endif %}
                                {% endfor %}
                            </div>
                            <div class="col-md-6">
                                <h6>JSON Editor</h6>
                                <div id="data-editor" style="height: 300px;"></div>
                                <textarea name="data" id="data" class="d-none"></textarea>
                            </div>
                        </div>
                        <button type="button" class="btn btn-secondary mb-3" onclick="previewChanges()">Preview Changes</button>
                        <pre id="preview" class="border p-3 mb-3"></pre>
                        <button type="submit" class="btn btn-primary" onclick="document.getElementById('data').value = ace.edit('data-editor').getValue();"><i class="fas fa-save me-2"></i>Save Changes</button>
                        <a href="{{ url_for('fluxdbadminview.collection', collection_name=collection) }}" class="btn btn-secondary">Cancel</a>
                    </form>
                </div>
            </div>
        </div>
        {{ COOKIE_CONSENT_HTML | safe }}
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
</html>
"""

AGGREGATE_HTML = """
<html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=1200">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="/static/css/style.css" rel="stylesheet">
        <script src="https://kit.fontawesome.com/a076d05399.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/ace-builds@1.32.9/src-min-noconflict/ace.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/ace-builds@1.32.9/src-min-noconflict/mode-json.js"></script>
        <script>
            function showCookieConsent() {
                if (!{{ cookie_consent|tojson }}) {
                    document.getElementById('cookieConsentModal').style.display = 'block';
                }
            }
            window.onload = function() {
                showCookieConsent();
                var editor = ace.edit("pipeline-editor");
                editor.setTheme("ace/theme/{{ 'chrome' if theme == 'light' else 'monokai' }}");
                editor.session.setMode("ace/mode/json");
                editor.setOptions({ maxLines: 20, minLines: 10 });
                editor.setValue(JSON.stringify({{ pipeline | tojson }}, null, 2));
            };
        </script>
    </head>
    <body class="{{ 'bg-light' if theme == 'light' else 'bg-dark text-light' }}">
        <nav class="navbar navbar-expand-lg {{ 'navbar-light bg-primary' if theme == 'light' else 'navbar-dark bg-dark' }}">
            <div class="container" style="max-width: 1200px;">
                <a class="navbar-brand" href="{{ url_for('fluxdbadminview.index') }}">FluxDB Admin</a>
                <div class="navbar-nav ms-auto">
                    <form method="post" action="{{ url_for('set_theme') }}" class="d-inline">
                        <select name="theme" onchange="this.form.submit()" class="form-select form-select-sm">
                            <option value="light" {{ 'selected' if theme == 'light' }}>Light</option>
                            <option value="dark" {{ 'selected' if theme == 'dark' }}>Dark</option>
                        </select>
                    </form>
                    <a class="nav-link" href="{{ url_for('logout') }}">Logout</a>
                </div>
            </div>
        </nav>
        <div class="container mt-4" style="max-width: 1200px;">
            <h1 class="mb-4">Aggregate: {{ collection }}</h1>
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
                    <h5 class="card-title">Aggregation Pipeline</h5>
                    <form method="post">
                        <div class="mb-3">
                            <label for="pipeline-editor" class="form-label">Pipeline (JSON array, e.g., [{"$match": {"field": "value"}}])</label>
                            <div id="pipeline-editor" style="height: 200px;"></div>
                            <textarea name="pipeline" id="pipeline" class="d-none"></textarea>
                        </div>
                        <button type="submit" class="btn btn-primary" onclick="document.getElementById('pipeline').value = ace.edit('pipeline-editor').getValue();"><i class="fas fa-chart-bar me-2"></i>Run Aggregation</button>
                    </form>
                </div>
            </div>
            {% if results %}
                <h3>Results</h3>
                <div class="table-responsive">
                    <table class="table table-striped table-hover">
                        <thead>
                            <tr>
                                <th>Data</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for result in results %}
                                <tr>
                                    <td><pre>{{ result | tojson(indent=2) }}</pre></td>
                                </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            {% else %}
                <p class="text-muted">No results.</p>
            {% endif %}
        </div>
        {{ COOKIE_CONSENT_HTML | safe }}
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
</html>
"""

COOKIE_CONSENT_HTML = """
<div id="cookieConsentModal" style="display: none; position: fixed; bottom: 0; width: 100%; background: {{ '#f8f9fa' if theme == 'light' else '#343a40' }}; padding: 20px; box-shadow: 0 -2px 5px rgba(0,0,0,0.2); z-index: 1000;">
    <div class="container" style="max-width: 1200px;">
        <h5>We use cookies</h5>
        <p>We use essential cookies to ensure the website works properly and optional cookies to save your preferences (e.g., theme). Please choose your cookie settings:</p>
        <form method="post" action="{{ url_for('cookie_consent') }}">
            <div class="form-check mb-3">
                <input type="radio" name="consent" value="essential" id="essential" checked>
                <label for="essential">Only essential cookies (required for login and session)</label>
            </div>
            <div class="form-check mb-3">
                <input type="radio" name="consent" value="all" id="all">
                <label for="all">Accept all cookies (includes preferences like theme)</label>
            </div>
            <button type="submit" class="btn btn-primary">Save Preferences</button>
        </form>
    </div>
</div>
"""

STYLE_CSS = """
body {
    background-color: #f8f9fa;
    min-width: 1200px;
}

body.bg-dark {
    background-color: #212529;
    color: #f8f9fa;
}

.card {
    transition: transform 0.2s;
    background-color: #fff;
}

body.bg-dark .card {
    background-color: #343a40;
    color: #f8f9fa;
}

.card:hover {
    transform: translateY(-5px);
}

.list-group-item {
    transition: background-color 0.2s;
    background-color: #fff;
}

body.bg-dark .list-group-item {
    background-color: #343a40;
    color: #f8f9fa;
}

.list-group-item:hover {
    background-color: #e9ecef;
}

body.bg-dark .list-group-item:hover {
    background-color: #495057;
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

body.bg-dark .navbar {
    background-color: #343a40 !important;
}

.table {
    background-color: #fff;
}

body.bg-dark .table {
    background-color: #343a40;
    color: #f8f9fa;
}

.table-striped > tbody > tr:nth-of-type(odd) {
    background-color: #f9f9f9;
}

body.bg-dark .table-striped > tbody > tr:nth-of-type(odd) {
    background-color: #495057;
}

.form-control {
    background-color: #fff;
}

body.bg-dark .form-control {
    background-color: #495057;
    color: #f8f9fa;
    border-color: #6c757d;
}

#data-editor, #update-editor, #pipeline-editor {
    border: 1px solid #ced4da;
    border-radius: 4px;
}

body.bg-dark #data-editor, body.bg-dark #update-editor, body.bg-dark #pipeline-editor {
    border-color: #6c757d;
}
"""
