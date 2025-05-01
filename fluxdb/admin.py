from flask import Flask, request, redirect, url_for, session, flash, Response, render_template_string
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.base import BaseView
from flask_admin.contrib.fileadmin import FileAdmin
from functools import wraps
import os
import json
from .htmlsite import INDEX_HTML, COLLECTION_HTML, EDIT_HTML, STYLE_CSS

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'logged_in' not in session:
            flash("Please log in to access the FluxDB Admin.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

class FluxDBAdminView(BaseView):
    def __init__(self, db, **kwargs):
        self.db = db
        super().__init__(name=kwargs.get('name'), endpoint=kwargs.get('endpoint'))

    @expose('/')
    @require_auth
    def index(self):
        collections = self.db.list_collections()
        return render_template_string(INDEX_HTML, collections=collections)

    @expose('/create_collection', methods=['POST'])
    @require_auth
    def create_collection(self):
        name = request.form.get('name')
        if not name:
            flash("Collection name cannot be empty.", "danger")
            return redirect(url_for('fluxdbadminview.index'))
        try:
            self.db.create_collection(name)
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
        if request.method == 'POST':
            try:
                data = json.loads(request.form.get('data', '{}'))
                if not isinstance(data, dict):
                    flash("Invalid record format. Use JSON object.", "danger")
                else:
                    self.db.insert(collection_name, data)
                    flash(f"Record added to {collection_name}.", "success")
            except json.JSONDecodeError:
                flash("Invalid JSON format.", "danger")
            return redirect(url_for('fluxdbadminview.collection', collection_name=collection_name))
        records = self.db.find(collection_name)
        return render_template_string(COLLECTION_HTML, collection=collection_name, records=records)

    @expose('/collection/<collection_name>/edit/<record_id>', methods=['GET', 'POST'])
    @require_auth
    def edit(self, collection_name, record_id):
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
        return render_template_string(EDIT_HTML, collection=collection_name, record=record, record_id=record_id)

    @expose('/collection/<collection_name>/delete/<record_id>')
    @require_auth
    def delete(self, collection_name, record_id):
        if self.db.delete(collection_name, record_id):
            flash(f"Record {record_id} deleted from {collection_name}.", "success")
        else:
            flash(f"Record {record_id} not found in {collection_name}.", "danger")
        return redirect(url_for('fluxdbadminview.collection', collection_name=collection_name))

class CustomAdminIndexView(AdminIndexView):
    @expose('/')
    @require_auth
    def index(self):
        from fluxdb import FluxDB
        db = FluxDB(os.path.join(os.path.dirname(__file__), 'data'))
        collections = db.list_collections()
        return render_template_string(INDEX_HTML, collections=collections)

def start_admin_server(db_path, host='0.0.0.0', port=5000):
    from fluxdb import FluxDB
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'fluxdb-secret-123'  # Change to a secure key in production
    admin = Admin(
        app,
        name='FluxDB Admin',
        template_mode='bootstrap5',
        index_view=CustomAdminIndexView(url='/admin')
    )

    db = FluxDB(db_path)
    admin.add_view(FluxDBAdminView(db, name='Collections', endpoint='fluxdbadminview'))

    db_dir = os.path.dirname(db_path) or '.'
    admin.add_view(FileAdmin(db_dir, name='Database Files'))

    @app.route('/')
    def index():
        return redirect(url_for('admin.index'))

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            password = request.form.get('password')
            if password == 'admin123':  # Replace with a secure password
                session['logged_in'] = True
                flash('Logged in successfully!', 'success')
                return redirect(url_for('admin.index'))
            flash('Invalid password.', 'danger')
        return render_template_string("""
            <html>
                <head>
                    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
                    <link href="/static/css/style.css" rel="stylesheet">
                </head>
                <body class="bg-light">
                    <div class="container mt-5">
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
                    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
                </body>
            </html>
        """)

    @app.route('/static/css/style.css')
    def serve_css():
        return Response(STYLE_CSS, mimetype='text/css')

    @app.route('/logout')
    def logout():
        session.pop('logged_in', None)
        flash('Logged out.', 'info')
        return redirect(url_for('login'))

    app.run(host=host, port=port, debug=True)
