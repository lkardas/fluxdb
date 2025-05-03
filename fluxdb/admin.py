import os
import secrets
import json
import logging
import threading
import csv
from io import StringIO
from flask import Flask, request, redirect, url_for, session, flash, Response, render_template_string
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.fileadmin import FileAdmin
from functools import wraps
from .htmlsite import INDEX_HTML, COLLECTION_HTML, EDIT_HTML, STYLE_CSS, COOKIE_CONSENT_HTML, AGGREGATE_HTML

class NoLoggingFilter(logging.Filter):
    def filter(self, record):
        return False

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'logged_in' not in session:
            flash("Please log in to access the FluxDB Admin.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

class FluxDBAdminView(AdminIndexView):
    def __init__(self, db, **kwargs):
        self.db = db
        super().__init__(name=kwargs.get('name'), endpoint=kwargs.get('endpoint'))

    @expose('/')
    @require_auth
    def index(self):
        collections = self.db.list_collections()
        stats = {
            'collections': len(collections),
            'total_records': sum(self.db.count(c) for c in collections),
            'db_size': sum(os.path.getsize(os.path.join(self.db.db_path, c)) for c in collections if os.path.exists(os.path.join(self.db.db_path, c)))
        }
        theme = session.get('theme', 'light')
        cookie_consent = session.get('cookie_consent', False)
        return render_template_string(
            INDEX_HTML,
            collections=collections,
            stats=stats,
            theme=theme,
            cookie_consent=cookie_consent
        )

    @expose('/create_collection', methods=['POST'])
    @require_auth
    def create_collection(self):
        name = request.form.get('name')
        indexed_fields = request.form.get('indexed_fields', '').split(',')
        indexed_fields = [f.strip() for f in indexed_fields if f.strip()]
        if not name:
            flash("Collection name cannot be empty.", "danger")
            return redirect(url_for('fluxdbadminview.index'))
        try:
            self.db.create_collection(name, indexed_fields)
            flash(f"Collection {name} created.", "success")
        except ValueError as e:
            flash(str(e), "danger")
        return redirect(url_for('fluxdbadminview.index'))

    @expose('/drop_collection/<collection_name>')
    @require_auth
    def drop_collection(self, collection_name):
        try:
            self.db.drop_collection(collection_name)
            flash(f"Collection {collection_name} deleted.", "success")
        except Exception as e:
            flash(f"Error deleting collection {collection_name}: {str(e)}", "danger")
        return redirect(url_for('fluxdbadminview.index'))

    @expose('/collection/<collection_name>', methods=['GET', 'POST'])
    @require_auth
    def collection(self, collection_name):
        theme = session.get('theme', 'light')
        cookie_consent = session.get('cookie_consent', False)
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        sort_field = request.args.get('sort', '_id')
        sort_dir = int(request.args.get('sort_dir', 1))
        query = request.args.get('query', '{}')
        try:
            query = json.loads(query) if query else {}
        except json.JSONDecodeError:
            flash("Invalid query JSON format.", "danger")
            query = {}

        if request.method == 'POST':
            action = request.form.get('action')
            if action == 'insert':
                try:
                    data = json.loads(request.form.get('data', '{}'))
                    if not isinstance(data, dict):
                        flash("Invalid record format. Use JSON object.", "danger")
                    else:
                        self.db.insert(collection_name, data)
                        flash(f"Record added to {collection_name}.", "success")
                except json.JSONDecodeError:
                    flash("Invalid JSON format.", "danger")
            elif action == 'bulk_insert':
                if 'file' in request.files and request.files['file'].filename:
                    file = request.files['file']
                    if file.filename.endswith('.json'):
                        data = json.load(file)
                        if not isinstance(data, list):
                            flash("JSON file must contain a list of objects.", "danger")
                        else:
                            self.db.insert_many(collection_name, data)
                            flash(f"Inserted {len(data)} records to {collection_name}.", "success")
                    elif file.filename.endswith('.csv'):
                        csv_data = file.read().decode('utf-8')
                        reader = csv.DictReader(StringIO(csv_data))
                        records = [dict(row) for row in reader]
                        self.db.insert_many(collection_name, records)
                        flash(f"Inserted {len(records)} records to {collection_name}.", "success")
                    else:
                        flash("Unsupported file format. Use JSON or CSV.", "danger")
                else:
                    flash("No file uploaded.", "danger")
            elif action == 'bulk_delete':
                record_ids = request.form.getlist('record_ids')
                for record_id in record_ids:
                    self.db.delete(collection_name, record_id)
                flash(f"Deleted {len(record_ids)} records from {collection_name}.", "success")
            elif action == 'bulk_update':
                try:
                    update_data = json.loads(request.form.get('update_data', '{}'))
                    record_ids = request.form.getlist('record_ids')
                    for record_id in record_ids:
                        self.db.update(collection_name, record_id, update_data)
                    flash(f"Updated {len(record_ids)} records in {collection_name}.", "success")
                except json.JSONDecodeError:
                    flash("Invalid update JSON format.", "danger")
            return redirect(url_for('fluxdbadminview.collection', collection_name=collection_name))

        skip = (page - 1) * per_page
        sort = {sort_field: sort_dir} if sort_field else None
        records = self.db.find(collection_name, query, limit=per_page, skip=skip, sort=sort)
        total_records = self.db.count(collection_name, query)
        total_pages = (total_records + per_page - 1) // per_page
        indexes = self.db.index_manager.list_indexes(collection_name) if hasattr(self.db, 'index_manager') else []
        fields = set()
        for record in self.db.find(collection_name, limit=10):
            fields.update(record.keys())

        return render_template_string(
            COLLECTION_HTML,
            collection=collection_name,
            records=records,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            sort_field=sort_field,
            sort_dir=sort_dir,
            query=query,
            theme=theme,
            cookie_consent=cookie_consent,
            indexes=indexes,
            fields=fields
        )

    @expose('/collection/<collection_name>/edit/<record_id>', methods=['GET', 'POST'])
    @require_auth
    def edit(self, collection_name, record_id):
        theme = session.get('theme', 'light')
        cookie_consent = session.get('cookie_consent', False)
        if request.method == 'POST':
            try:
                data = json.loads(request.form.get('data', '{}'))
                if not isinstance(data, dict):
                    flash("Invalid record format. Use JSON object.", "danger")
                else:
                    self.db.update(collection_name, record_id, data)
                    flash(f"Record {record_id} updated in {collection_name}.", "success")
                    return redirect(url_for('fluxdbadminview.collection', collection_name=collection_name))
            except json.JSONDecodeError:
                flash("Invalid JSON format.", "danger")
        records = self.db.find(collection_name, {'_id': record_id})
        record = records[0] if records else {}
        fields = record.keys() if record else []
        return render_template_string(
            EDIT_HTML,
            collection=collection_name,
            record=record,
            record_id=record_id,
            theme=theme,
            cookie_consent=cookie_consent,
            fields=fields
        )

    @expose('/collection/<collection_name>/delete/<record_id>')
    @require_auth
    def delete(self, collection_name, record_id):
        if self.db.delete(collection_name, record_id):
            flash(f"Record {record_id} deleted from {collection_name}.", "success")
        else:
            flash(f"Record {record_id} not found in {collection_name}.", "danger")
        return redirect(url_for('fluxdbadminview.collection', collection_name=collection_name))

    @expose('/collection/<collection_name>/export', methods=['GET'])
    @require_auth
    def export(self, collection_name):
        output_file = f"{collection_name}_export.fdb"
        if self.db.export_collection(collection_name, output_file):
            with open(output_file, 'rb') as f:
                response = Response(f.read(), mimetype='application/octet-stream')
                response.headers['Content-Disposition'] = f'attachment; filename={output_file}'
                return response
        flash(f"Failed to export {collection_name}.", "danger")
        return redirect(url_for('fluxdbadminview.collection', collection_name=collection_name))

    @expose('/collection/<collection_name>/import', methods=['POST'])
    @require_auth
    def import_collection(self, collection_name):
        if 'file' not in request.files:
            flash("No file uploaded.", "danger")
            return redirect(url_for('fluxdbadminview.collection', collection_name=collection_name))
        file = request.files['file']
        if file.filename == '':
            flash("No file selected.", "danger")
            return redirect(url_for('fluxdbadminview.collection', collection_name=collection_name))
        input_file = f"{collection_name}_import.fdb"
        file.save(input_file)
        if self.db.import_collection(collection_name, input_file):
            flash(f"Collection {collection_name} imported.", "success")
        else:
            flash(f"Failed to import {collection_name}.", "danger")
        os.remove(input_file)
        return redirect(url_for('fluxdbadminview.collection', collection_name=collection_name))

    @expose('/collection/<collection_name>/indexes', methods=['GET', 'POST'])
    @require_auth
    def manage_indexes(self, collection_name):
        theme = session.get('theme', 'light')
        cookie_consent = session.get('cookie_consent', False)
        if request.method == 'POST':
            action = request.form.get('action')
            field = request.form.get('field')
            if action == 'add' and field:
                try:
                    self.db.index_manager.create_index(collection_name, field)
                    flash(f"Index on {field} created for {collection_name}.", "success")
                except Exception as e:
                    flash(f"Error creating index: {str(e)}", "danger")
            elif action == 'delete' and field:
                try:
                    self.db.index_manager.drop_index(collection_name, field)
                    flash(f"Index on {field} deleted for {collection_name}.", "success")
                except Exception as e:
                    flash(f"Error deleting index: {str(e)}", "danger")
        indexes = self.db.index_manager.list_indexes(collection_name) if hasattr(self.db, 'index_manager') else []
        return render_template_string(
            """
            <html>
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=1200">
                    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
                    <link href="/static/css/style.css" rel="stylesheet">
                    <script src="https://kit.fontawesome.com/a076d05399.js"></script>
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
                        <h1 class="mb-4">Manage Indexes for {{ collection_name }}</h1>
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
                                <h5 class="card-title">Add New Index</h5>
                                <form method="post">
                                    <input type="hidden" name="action" value="add">
                                    <div class="input-group">
                                        <input type="text" name="field" class="form-control" placeholder="Field name" required>
                                        <button type="submit" class="btn btn-primary"><i class="fas fa-plus"></i> Add</button>
                                    </div>
                                </form>
                            </div>
                        </div>
                        <h3>Existing Indexes</h3>
                        {% if indexes %}
                            <div class="list-group">
                                {% for index in indexes %}
                                    <div class="list-group-item d-flex justify-content-between align-items-center">
                                        <span>{{ index }}</span>
                                        <form method="post">
                                            <input type="hidden" name="action" value="delete">
                                            <input type="hidden" name="field" value="{{ index }}">
                                            <button type="submit" class="btn btn-sm btn-danger" onclick="return confirm('Are you sure you want to delete index {{ index }}?')">
                                                <i class="fas fa-trash"></i> Delete
                                            </button>
                                        </form>
                                    </div>
                                {% endfor %}
                            </div>
                        {% else %}
                            <p class="text-muted">No indexes found.</p>
                        {% endif %}
                    </div>
                    {{ COOKIE_CONSENT_HTML | safe }}
                    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
                </body>
            </html>
            """,
            collection_name=collection_name,
            indexes=indexes,
            theme=theme,
            cookie_consent=cookie_consent
        )

    @expose('/collection/<collection_name>/aggregate', methods=['GET', 'POST'])
    @require_auth
    def aggregate(self, collection_name):
        theme = session.get('theme', 'light')
        cookie_consent = session.get('cookie_consent', False)
        results = []
        pipeline = []
        if request.method == 'POST':
            try:
                pipeline = json.loads(request.form.get('pipeline', '[]'))
                if not isinstance(pipeline, list):
                    flash("Pipeline must be a JSON array.", "danger")
                else:
                    results = self.db.aggregate(collection_name, pipeline)
                    flash("Aggregation executed successfully.", "success")
            except json.JSONDecodeError:
                flash("Invalid pipeline JSON format.", "danger")
        return render_template_string(
            AGGREGATE_HTML,
            collection=collection_name,
            results=results,
            pipeline=pipeline,
            theme=theme,
            cookie_consent=cookie_consent
        )

    @expose('/collection/<collection_name>/transaction', methods=['POST'])
    @require_auth
    def transaction(self, collection_name):
        action = request.form.get('action')
        try:
            if action == 'begin':
                self.db.begin_transaction()
                flash("Transaction started.", "success")
            elif action == 'commit':
                self.db.commit()
                flash("Transaction committed.", "success")
            elif action == 'rollback':
                self.db.rollback()
                flash("Transaction rolled back.", "success")
        except Exception as e:
            flash(f"Transaction error: {str(e)}", "danger")
        return redirect(url_for('fluxdbadminview.collection', collection_name=collection_name))

def start_admin_server(db_path: str, host: str, port: int, debug: bool, admin_password: str = None, secret_key: str = None):
    server = AdminServer(db_path, host, port, debug, admin_password, secret_key)
    server.start()

class AdminServer:
    def __init__(
        self,
        db_path: str,
        host: str = '0.0.0.0',
        port: int = 5000,
        debug: bool = False,
        admin_password: str = None,
        secret_key: str = None
    ):
        self.db_path = db_path
        self.host = host
        self.port = port
        self.debug = debug
        self.admin_password = admin_password
        self.secret_key = secret_key
        self.app = None
        self.flask_thread = None
        self.setup_flask()

    def setup_flask(self):
        from .fluxdb import FluxDB

        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = (
            self.secret_key or
            os.environ.get('FLUXDB_SECRET_KEY') or
            secrets.token_hex(32)
        )
        self.app.config['PERMANENT_SESSION_LIFETIME'] = 2592000

        admin = Admin(
            self.app,
            name='FluxDB Admin',
            template_mode='bootstrap5',
            index_view=FluxDBAdminView(FluxDB(self.db_path), url='/admin', endpoint='fluxdbadminview')
        )

        db_dir = os.path.dirname(self.db_path) or '.'
        admin.add_view(FileAdmin(db_dir, name='Database Files'))

        @self.app.route('/')
        def index():
            return redirect(url_for('fluxdbadminview.index'))

        @self.app.route('/login', methods=['GET', 'POST'])
        def login():
            ADMIN_PASSWORD = (
                self.admin_password or
                os.environ.get('FLUXDB_ADMIN_PASSWORD') or
                'admin123'
            )
            theme = session.get('theme', 'light')
            cookie_consent = session.get('cookie_consent', False)
            if request.method == 'POST':
                password = request.form.get('password')
                if password == ADMIN_PASSWORD:
                    session['logged_in'] = True
                    session.permanent = True
                    flash('Logged in successfully!', 'success')
                    return redirect(url_for('fluxdbadminview.index'))
                flash('Invalid password.', 'danger')
            return render_template_string(
                """
                <html>
                    <head>
                        <meta charset="UTF-8">
                        <meta name="viewport" content="width=1200">
                        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
                        <link href="/static/css/style.css" rel="stylesheet">
                        <script src="https://kit.fontawesome.com/a076d05399.js"></script>
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
                        <div class="container mt-5" style="max-width: 1200px;">
                            <div class="card shadow-sm p-4" style="max-width: 400px; margin: auto;">
                                <h2 class="text-center mb-4">FluxDB Admin Login</h2>
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
                                <form method="post">
                                    <div class="mb-3">
                                        <label for="password" class="form-label">Password</label>
                                        <input type="password" name="password" id="password" class="form-control" required>
                                    </div>
                                    <button type="submit" class="btn btn-primary w-100">Login</button>
                                </form>
                            </div>
                        </div>
                        {{ COOKIE_CONSENT_HTML | safe }}
                        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
                    </body>
                </html>
                """,
                theme=theme,
                cookie_consent=cookie_consent
            )

        @self.app.route('/cookie_consent', methods=['POST'])
        def cookie_consent():
            consent = request.form.get('consent', 'essential')
            session['cookie_consent'] = consent == 'all'
            session.permanent = True
            flash("Cookie preferences saved.", "success")
            return redirect(request.referrer or url_for('fluxdbadminview.index'))

        @self.app.route('/set_theme', methods=['POST'])
        @require_auth
        def set_theme():
            if session.get('cookie_consent', False):
                theme = request.form.get('theme', 'light')
                session['theme'] = theme
                flash(f"Theme set to {theme}.", "success")
            else:
                flash("Enable cookies to save theme preferences.", "warning")
            return redirect(request.referrer or url_for('fluxdbadminview.index'))

        @self.app.route('/static/css/style.css')
        def serve_css():
            return Response(STYLE_CSS, mimetype='text/css')

        @self.app.route('/logout')
        def logout():
            session.pop('logged_in', None)
            session.pop('theme', None)
            flash('Logged out.', 'info')
            return redirect(url_for('login'))

        if not self.debug:
            log = logging.getLogger('werkzeug')
            log.setLevel(logging.ERROR)
            log.addFilter(NoLoggingFilter())

    def start(self):
        def run_flask():
            import sys
            if not self.debug:
                null_file = os.devnull if os.name != 'nt' else 'NUL'
                sys.stdout = open(null_file, 'w')
                sys.stderr = open(null_file, 'w')
            self.app.run(host=self.host, port=self.port, debug=self.debug, use_reloader=False)

        self.flask_thread = threading.Thread(target=run_flask, daemon=True)
        self.flask_thread.start()
