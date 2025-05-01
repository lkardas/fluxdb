from flask import Flask, request, redirect, url_for, session, flash
from flask_admin import Admin, AdminIndexView
from flask_admin.contrib import BaseView
from flask_admin.contrib.fileadmin import FileAdmin
from fluxdb import FluxDB
from functools import wraps
import os
import json

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
        super().__init__(**kwargs)

    @expose('/')
    @require_auth
    def index(self):
        collections = self.db.list_collections()
        return self.render('admin/index.html', collections=collections)

    @expose('/collection/<name>', methods=['GET', 'POST'])
    @require_auth
    def collection(self, name):
        if request.method == 'POST':
            try:
                # Expect JSON-like input (e.g., {"name": "value"})
                data = json.loads(request.form.get('data', '{}'))
                if not isinstance(data, dict):
                    flash("Invalid record format. Use JSON object.", "danger")
                else:
                    self.db.insert(name, data)
                    flash(f"Record added to {name}.", "success")
            except json.JSONDecodeError:
                flash("Invalid JSON format.", "danger")
            return redirect(url_for('fluxdbadminview.collection', name=name))
        records = self.db.find(name)
        return self.render('admin/collection.html', collection=name, records=records)

    @expose('/collection/<name>/edit/<record_id>', methods=['GET', 'POST'])
    @require_auth
    def edit(self, name, record_id):
        if request.method == 'POST':
            try:
                data = json.loads(request.form.get('data', '{}'))
                if not isinstance(data, dict):
                    flash("Invalid record format. Use JSON object.", "danger")
                else:
                    self.db.update(name, record_id, data)
                    flash(f"Record {record_id} updated in {name}.", "success")
                    return redirect(url_for('fluxdbadminview.collection', name=name))
            except json.JSONDecodeError:
                flash("Invalid JSON format.", "danger")
        records = self.db.find(name, {'_id': record_id})
        record = records[0] if records else {}
        return self.render('admin/edit.html', collection=name, record=record, record_id=record_id)

    @expose('/collection/<name>/delete/<record_id>')
    @require_auth
    def delete(self, name, record_id):
        if self.db.delete(name, record_id):
            flash(f"Record {record_id} deleted from {name}.", "success")
        else:
            flash(f"Record {record_id} not found in {name}.", "danger")
        return redirect(url_for('fluxdbadminview.collection', name=name))

class CustomAdminIndexView(AdminIndexView):
    @expose('/')
    @require_auth
    def index(self):
        return super().index()

def start_admin_server(db_path, host='0.0.0.0', port=5000):
    app = Flask(__name__, static_folder='static', static_url_path='/static')
    app.config['SECRET_KEY'] = 'fluxdb-secret-123'  # Change to a secure key in production
    admin = Admin(
        app,
        name='FluxDB Admin',
        template_mode='bootstrap5',
        index_view=CustomAdminIndexView()
    )

    db = FluxDB(db_path)
    admin.add_view(FluxDBAdminView(db, name='Collections', endpoint='fluxdbadminview'))

    db_dir = os.path.dirname(db_path) or '.'
    admin.add_view(FileAdmin(db_dir, name='Database Files'))

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            password = request.form.get('password')
            if password == 'admin123':  # Replace with a secure password
                session['logged_in'] = True
                flash('Logged in successfully!', 'success')
                return redirect(url_for('admin.index'))
            flash('Invalid password.', 'danger')
        return '''
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
        '''

    @app.route('/logout')
    def logout():
        session.pop('logged_in', None)
        flash('Logged out.', 'info')
        return redirect(url_for('login'))

    app.run(host=host, port=port, debug=True)
