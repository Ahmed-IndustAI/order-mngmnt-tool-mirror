"""
Broadsens Order Management Tool
===============================
A comprehensive web-based tool for managing Broadsens sensor orders,
customer information, site data, and automatic sensor ID assignments.

Features:
- Customer, Site, and Order Management with full CRUD operations
- Broadsens Sensor Catalog Management  
- Order Creation and Tracking (all orders treated as active)
- Automatic Sensor ID and Group ID Assignment
- Duplicate Prevention (per sensor type per site)
- PO/Invoice Tracking
- Sensor ID filtering by customer and site
- Excel Database Export
- Usage Analytics

Updated with edit functionality and improved filtering.
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import LoginManager, UserMixin
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, Regexp
from werkzeug.security import generate_password_hash, check_password_hash
from urllib.parse import urlparse, urljoin
import json
import os
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict
import uuid
import pandas as pd
import re
import tempfile


app = Flask(__name__)
app.secret_key = os.environ.get('SESSION_SECRET')
if not app.secret_key:
    raise RuntimeError("SESSION_SECRET environment variable must be set for security")

# Ensure sessions work properly
app.config['SESSION_TYPE'] = 'filesystem'

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access the BroadSens Sensor Management Tool.'
login_manager.session_protection = None  # Disable session protection for debugging

# Initialize CSRF Protection - disabled for token-based auth
# csrf = CSRFProtect(app)

# Add CSRF error handler to help debug issues
@app.errorhandler(400)
def csrf_error(reason):
    return render_template('csrf_error.html', reason=reason), 400

# Configure session and CSRF settings
app.config.update(
    WTF_CSRF_TIME_LIMIT=None,  # No time limit for CSRF tokens
    SESSION_COOKIE_SECURE=True,  # Required for SameSite=None
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='None',  # Allow cross-site cookies in iframe
    REMEMBER_COOKIE_SECURE=True,  # Required for SameSite=None
    REMEMBER_COOKIE_HTTPONLY=True,
    REMEMBER_COOKIE_SAMESITE='None'  # Allow cross-site remember cookies
)


def is_email_allowed(email):
    """Check if email is allowed for registration"""
    return db.is_email_allowed(email)

# Broadsens Sensor Catalog - Updated with actual products
BROADSENS_SENSOR_CATALOG = {
    "SVT-A": {
        "name": "SVT-A Type (Acceleration Sensors)",
        "description": "Wireless vibration & temperature sensors with acceleration measurement, including long range variants",
        "models": [
            "SVT200-A", "SVT300-A", "SVT400-A", 
            "SVT200-LA", "SVT300-LA", "SVT400-LA"
        ]
    },
    "SVT-V": {
        "name": "SVT-V Type (Velocity Sensors)", 
        "description": "Wireless vibration sensors with velocity measurement, including long range variants",
        "models": [
            "SVT200-V", "SVT300-V", "SVT400-V",
            "SVT200-LV", "SVT300-LV", "SVT400-LV"
        ]
    },
    "SVT-T": {
        "name": "SVT-T Type (High Temperature Sensors)",
        "description": "Wireless high temperature sensors (-40 to 105°C)",
        "models": ["SVT200-T"]
    },
    "SVT-C": {
        "name": "SVT-C Type (Cabled Power Sensors)",
        "description": "Wireless vibration sensors with power supply cable",
        "models": ["SVT200-CA", "SVT200-CV", "SVT300-CA", "SVT300-CV"]
    },
    "WOS": {
        "name": "WOS Type (Optical Speed Sensors)",
        "description": "Wireless optical speed sensors",
        "models": ["WOS200"]
    }
}

# Authentication Forms - CSRF disabled temporarily
class LoginForm(FlaskForm):
    class Meta:
        csrf = False
    
    email = StringField('Email', validators=[
        DataRequired(), 
        Regexp(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', 
               message="Please enter a valid email address")
    ])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign In')

class RegisterForm(FlaskForm):
    class Meta:
        csrf = False
    
    email = StringField('Email', validators=[
        DataRequired(), 
        Regexp(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', 
               message="Please enter a valid email address")
    ])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    submit = SubmitField('Register')

# User Model for Authentication
class User(UserMixin):
    def __init__(self, id, email, password_hash=None):
        self.id = id
        self.email = email
        self.password_hash = password_hash
    
    def get_id(self):
        """Return the user ID as a string - required by Flask-Login"""
        return str(self.id)
    
    def is_authenticated(self):
        return True
    
    def is_active(self):
        return True
    
    def is_anonymous(self):
        return False
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @staticmethod
    def create_user(email, password):
        user_id = str(uuid.uuid4())
        password_hash = generate_password_hash(password)
        return User(user_id, email, password_hash)

# Data Models
@dataclass
class Customer:
    id: str
    name: str
    contact_person: str
    email: str
    phone: str
    address: str
    created_at: str

@dataclass
class Site:
    id: str
    customer_id: str
    name: str
    location: str
    contact_person: str
    phone: str
    created_at: str

@dataclass
class SensorType:
    type_code: str
    name: str
    description: str
    models: List[str]

@dataclass
class Order:
    id: str
    customer_id: str
    site_id: str
    po_number: str
    invoice_number: str
    order_date: str
    sensors: List[Dict]  # [{"sensor_type": "SVT-A", "model": "SVT200-A", "quantity": 10}]
    notes: str

@dataclass
class UsedID:
    id: str
    customer_id: str
    site_id: str
    order_id: str
    sensor_type: str
    model: str
    sensor_id: int
    group_id: str
    assigned_date: str
    status: str



# Initialize database - DynamoDB only
from dynamodb_database import DynamoDBDatabase
db = DynamoDBDatabase()
print("✓ Using DynamoDB backend")
db.ensure_sensor_types_loaded()

# Security helper functions
def is_safe_url(target):
    """Check if the target URL is safe for redirects (same origin)"""
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    print(f"Loading user with ID: {user_id}")
    try:
        user = db.get_user_by_id(user_id)
        print(f"User loaded: {user}")
        if user:
            print(f"User loaded successfully: {user.email}")
        else:
            print("No user found for this ID")
        return user
    except Exception as e:
        print(f"Error loading user: {e}")
        return None

# Authentication Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.lower().strip()  # Normalize email
        user = db.get_user_by_email(email)
        if user and user.check_password(form.password.data):
            # Generate authentication token
            import secrets
            auth_token = secrets.token_urlsafe(32)
            
            # Store token in database instead of session
            db.save_user_token(auth_token, user.id, user.email)
            
            flash('Logged in successfully!', 'success')
            # Redirect with token in URL
            return redirect(url_for('dashboard', token=auth_token))
        flash('Invalid email or password', 'error')
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    
    # Debug CSRF token
    if request.method == 'POST':
        pass
        
    if form.validate_on_submit():
        email = form.email.data.lower().strip()  # Normalize email
        
        # Check if email is allowed
        if not is_email_allowed(email):
            flash('Registration is restricted. This email address is not authorized to register.', 'error')
            return render_template('register.html', form=form)
        
        user = db.create_user(email, form.password.data)
        if user:
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        flash('Email already exists', 'error')
    else:
        # Print form errors for debugging
        if form.errors:
            pass
    return render_template('register.html', form=form)

@app.route('/logout', methods=['POST'])
def logout():
    # Clear all authentication tokens (optional - tokens can expire)
    auth_token = request.args.get('token')
    if auth_token:
        db.delete_user_token(auth_token)
    
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

# Routes
def require_login():
    """Token-based authentication check"""
    auth_token = request.args.get('token')
    
    if not auth_token:
        flash('Please log in to access this page.', 'warning')
        return redirect(url_for('login'))
    
    # Check token in database
    user_token_data = db.get_user_token(auth_token)
    if not user_token_data:
        flash('Session expired. Please log in again.', 'warning')
        return redirect(url_for('login'))
    
    return None

def get_current_user():
    """Get current user from token"""
    auth_token = request.args.get('token')
    if not auth_token:
        return None
    
    user_data = db.get_user_token(auth_token)
    return user_data

@app.context_processor
def inject_auth_token():
    """Make auth token available in all templates"""
    auth_token = request.args.get('token')
    current_user_data = get_current_user()
    return {
        'auth_token': auth_token,
        'current_user_data': current_user_data,
        'is_authenticated': current_user_data is not None
    }

@app.route('/')
def dashboard():
    # Check authentication first
    auth_check = require_login()
    if auth_check:
        return auth_check
    customers = db.get_customers()
    sites = db.get_sites()
    orders = db.get_orders()
    used_ids = db.get_used_ids()
    sensor_types = db.get_sensor_types()

    stats = {
        'total_customers': len(customers),
        'total_sites': len(sites),
        'total_orders': len(orders),
        'total_assigned_sensors': len(used_ids),
        'total_sensor_types': len(sensor_types)
    }

    recent_customers = customers[-5:] if customers else []
    recent_orders = orders[-5:] if orders else []

    return render_template('dashboard.html', 
                         stats=stats,
                         customers=recent_customers,
                         recent_orders=recent_orders)

# Customer Routes
@app.route('/customers')
def customers():
    # Check authentication first
    auth_check = require_login()
    if auth_check:
        return auth_check
    customers = db.get_customers()
    return render_template('customers.html', customers=customers)

@app.route('/add_customer', methods=['GET', 'POST'])
def add_customer():
    # Check authentication first
    auth_check = require_login()
    if auth_check:
        return auth_check
    if request.method == 'POST':
        customer_data = {
            'name': request.form['name'],
            'contact_person': request.form['contact_person'],
            'email': request.form['email'],
            'phone': request.form['phone'],
            'address': request.form['address']
        }
        
        customer_id = db.add_customer(customer_data)
        flash('Customer added successfully!', 'success')
        auth_token = request.args.get('token')
        return redirect(url_for('customers', token=auth_token))
    
    auth_token = request.args.get('token')
    return render_template('add_customer.html', auth_token=auth_token)

@app.route('/edit_customer/<customer_id>', methods=['GET', 'POST'])
def edit_customer(customer_id):
    # Check authentication first
    auth_check = require_login()
    if auth_check:
        return auth_check
    customer = db.get_customer(customer_id)
    if not customer:
        flash('Customer not found!', 'error')
        auth_token = request.args.get('token')
        return redirect(url_for('customers', token=auth_token))
    
    if request.method == 'POST':
        customer_data = {
            'name': request.form['name'],
            'contact_person': request.form['contact_person'],
            'email': request.form['email'],
            'phone': request.form['phone'],
            'address': request.form['address']
        }
        
        if db.update_customer(customer_id, customer_data):
            flash('Customer updated successfully!', 'success')
            auth_token = request.args.get('token')
            return redirect(url_for('customers', token=auth_token))
        else:
            flash('Error updating customer!', 'error')
    
    auth_token = request.args.get('token')
    return render_template('edit_customer.html', customer=customer, auth_token=auth_token)

# Site Routes
@app.route('/sites')
def sites():
    # Check authentication first
    auth_check = require_login()
    if auth_check:
        return auth_check
    customer_id = request.args.get('customer_id')
    sites = db.get_sites(customer_id)
    
    # Add customer names to sites for display
    customers = {c['id']: c['name'] for c in db.get_customers()}
    for site in sites:
        site['customer_name'] = customers.get(site['customer_id'], 'Unknown')
    
    return render_template('sites.html', sites=sites)

@app.route('/add_site', methods=['GET', 'POST'])
def add_site():
    # Check authentication first
    auth_check = require_login()
    if auth_check:
        return auth_check
    if request.method == 'POST':
        site_data = {
            'customer_id': request.form['customer_id'],
            'name': request.form['name'],
            'location': request.form['location'],
            'contact_person': request.form['contact_person'],
            'phone': request.form['phone']
        }
        
        site_id = db.add_site(site_data)
        flash('Site added successfully!', 'success')
        auth_token = request.args.get('token')
        return redirect(url_for('sites', token=auth_token))
    
    customers = db.get_customers()
    auth_token = request.args.get('token')
    return render_template('add_site.html', customers=customers, auth_token=auth_token)

@app.route('/edit_site/<site_id>', methods=['GET', 'POST'])
def edit_site(site_id):
    # Check authentication first
    auth_check = require_login()
    if auth_check:
        return auth_check
    site = db.get_site(site_id)
    if not site:
        flash('Site not found!', 'error')
        auth_token = request.args.get('token')
        return redirect(url_for('sites', token=auth_token))
    
    if request.method == 'POST':
        site_data = {
            'customer_id': request.form['customer_id'],
            'name': request.form['name'],
            'location': request.form['location'],
            'contact_person': request.form['contact_person'],
            'phone': request.form['phone']
        }
        
        if db.update_site(site_id, site_data):
            flash('Site updated successfully!', 'success')
            auth_token = request.args.get('token')
            return redirect(url_for('sites', token=auth_token))
        else:
            flash('Error updating site!', 'error')
    
    customers = db.get_customers()
    auth_token = request.args.get('token')
    return render_template('edit_site.html', site=site, customers=customers, auth_token=auth_token)

# Order Routes
@app.route('/orders')
def orders():
    # Check authentication first
    auth_check = require_login()
    if auth_check:
        return auth_check
    customer_id = request.args.get('customer_id')
    site_id = request.args.get('site_id')
    orders = db.get_orders(customer_id, site_id)
    
    # Add customer and site names to orders for display
    customers = {c['id']: c['name'] for c in db.get_customers()}
    sites = {s['id']: s['name'] for s in db.get_sites()}
    
    for order in orders:
        order['customer_name'] = customers.get(order['customer_id'], 'Unknown')
        order['site_name'] = sites.get(order['site_id'], 'Unknown')
    
    return render_template('orders.html', orders=orders)

@app.route('/create_order', methods=['GET', 'POST'])
def create_order():
    # Check authentication first
    auth_check = require_login()
    if auth_check:
        return auth_check
    if request.method == 'POST':
        # Parse multiple sensor items from form data
        sensors = []
        i = 0
        while f'sensor_type_{i}' in request.form:
            sensor_type = request.form.get(f'sensor_type_{i}')
            model = request.form.get(f'model_{i}')
            quantity = request.form.get(f'quantity_{i}')
            
            if sensor_type and model and quantity:
                sensors.append({
                    'sensor_type': sensor_type,
                    'model': model,
                    'quantity': int(quantity)
                })
            i += 1
        
        if not sensors:
            flash('Please add at least one sensor item to the order.', 'error')
            customers = db.get_customers()
            sensor_types = db.get_sensor_types()
            auth_token = request.args.get('token')
            return render_template('create_order.html', customers=customers, sensor_types=sensor_types, auth_token=auth_token)
        
        # Check for duplicate PO number for same customer-site combination
        customer_id = request.form['customer_id']
        site_id = request.form['site_id']
        po_number = request.form['po_number']
        
        if db.is_po_number_duplicate(customer_id, site_id, po_number):
            flash('Error: PO number already exists for this customer and site combination. Please use a different PO number.', 'error')
            customers = db.get_customers()
            sensor_types = db.get_sensor_types()
            auth_token = request.args.get('token')
            return render_template('create_order.html', customers=customers, sensor_types=sensor_types, auth_token=auth_token)
        
        order_data = {
            'customer_id': customer_id,
            'site_id': site_id,
            'po_number': po_number,
            'invoice_number': request.form['invoice_number'],
            'sensors': sensors,
            'notes': request.form['notes']
        }
        
        order_id = db.add_order(order_data)
        flash('Order created successfully! Sensor IDs have been automatically assigned.', 'success')
        auth_token = request.args.get('token')
        return redirect(url_for('order_details', order_id=order_id, token=auth_token))
    
    customers = db.get_customers()
    sensor_types = db.get_sensor_types()
    auth_token = request.args.get('token')
    return render_template('create_order.html', customers=customers, sensor_types=sensor_types, auth_token=auth_token)

@app.route('/edit_order/<order_id>', methods=['GET', 'POST'])
def edit_order(order_id):
    # Check authentication first
    auth_check = require_login()
    if auth_check:
        return auth_check
    order = db.get_order(order_id)
    if not order:
        flash('Order not found!', 'error')
        auth_token = request.args.get('token')
        return redirect(url_for('orders', token=auth_token))
    
    if request.method == 'POST':
        # Parse multiple sensor items from form data
        sensors = []
        i = 0
        while f'sensor_type_{i}' in request.form:
            sensor_type = request.form.get(f'sensor_type_{i}')
            model = request.form.get(f'model_{i}')
            quantity = request.form.get(f'quantity_{i}')
            
            if sensor_type and model and quantity:
                sensors.append({
                    'sensor_type': sensor_type,
                    'model': model,
                    'quantity': int(quantity)
                })
            i += 1
        
        if not sensors:
            flash('Please add at least one sensor item to the order.', 'error')
            customers = db.get_customers()
            sensor_types = db.get_sensor_types()
            auth_token = request.args.get('token')
            return render_template('edit_order.html', order=order, customers=customers, sensor_types=sensor_types, auth_token=auth_token)
        
        # Check for duplicate PO number for same customer-site combination (excluding current order)
        customer_id = request.form['customer_id']
        site_id = request.form['site_id']
        po_number = request.form['po_number']
        
        if db.is_po_number_duplicate(customer_id, site_id, po_number, exclude_order_id=order_id):
            flash('Error: PO number already exists for this customer and site combination. Please use a different PO number.', 'error')
            customers = db.get_customers()
            sensor_types = db.get_sensor_types()
            auth_token = request.args.get('token')
            return render_template('edit_order.html', order=order, customers=customers, sensor_types=sensor_types, auth_token=auth_token)
        
        order_data = {
            'customer_id': customer_id,
            'site_id': site_id,
            'po_number': po_number,
            'invoice_number': request.form['invoice_number'],
            'sensors': sensors,
            'notes': request.form['notes']
        }
        
        if db.update_order(order_id, order_data):
            flash('Order updated successfully! Sensor IDs have been reassigned if needed.', 'success')
            auth_token = request.args.get('token')
            return redirect(url_for('order_details', order_id=order_id, token=auth_token))
        else:
            flash('Error updating order!', 'error')
    
    customers = db.get_customers()
    sensor_types = db.get_sensor_types()
    auth_token = request.args.get('token')
    return render_template('edit_order.html', order=order, customers=customers, sensor_types=sensor_types, auth_token=auth_token)

@app.route('/order/<order_id>')
def order_details(order_id):
    # Check authentication first
    auth_check = require_login()
    if auth_check:
        return auth_check
    order = db.get_order(order_id)
    if not order:
        flash('Order not found!', 'error')
        auth_token = request.args.get('token')
        return redirect(url_for('orders', token=auth_token))
    
    customer = db.get_customer(order['customer_id'])
    site = db.get_site(order['site_id'])
    used_ids = db.get_used_ids(order['site_id'])
    used_ids = [u for u in used_ids if u['order_id'] == order_id]
    
    return render_template('order_details.html', 
                         order=order, 
                         customer=customer, 
                         site=site, 
                         used_ids=used_ids)

# Sensor Type Routes
@app.route('/sensor_types')
def sensor_types():
    # Check authentication first
    auth_check = require_login()
    if auth_check:
        return auth_check
    sensor_types = db.get_sensor_types()
    return render_template('sensor_types.html', sensor_types=sensor_types)

# Used IDs Routes with filtering
@app.route('/used_ids')
def used_ids():
    # Check authentication first
    auth_check = require_login()
    if auth_check:
        return auth_check
    customer_id = request.args.get('customer_id')
    site_id = request.args.get('site_id')
    sensor_type = request.args.get('sensor_type')
    
    used_ids = db.get_used_ids(site_id, sensor_type, customer_id)
    
    # Add customer and site names to used IDs for display
    customers = {c['id']: c['name'] for c in db.get_customers()}
    sites = {s['id']: s['name'] for s in db.get_sites()}
    
    for uid in used_ids:
        uid['customer_name'] = customers.get(uid['customer_id'], 'Unknown')
        uid['site_name'] = sites.get(uid['site_id'], 'Unknown')
    
    # Get filter options
    all_customers = db.get_customers()
    all_sites = db.get_sites()
    all_sensor_types = db.get_sensor_types()
    
    return render_template('used_ids.html', 
                         used_ids=used_ids,
                         customers=all_customers,
                         sites=all_sites, 
                         sensor_types=all_sensor_types,
                         selected_customer=customer_id,
                         selected_site=site_id,
                         selected_sensor_type=sensor_type)

# API Routes for dynamic forms
@app.route('/get_sites/<customer_id>')
def get_sites(customer_id):
    # Check authentication first
    auth_check = require_login()
    if auth_check:
        return auth_check
    sites = db.get_sites(customer_id)
    return jsonify(sites)

@app.route('/get_models/<sensor_type>')
def get_models(sensor_type):
    # Check authentication first
    auth_check = require_login()
    if auth_check:
        return auth_check
    sensor_types = db.get_sensor_types()
    for st in sensor_types:
        if st['type_code'] == sensor_type:
            return jsonify(st['models'])
    return jsonify([])

# Export Route
@app.route('/export_excel')
def export_excel():
    # Check authentication first
    auth_check = require_login()
    if auth_check:
        return auth_check
    try:
        # Create a temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
        temp_filename = temp_file.name
        temp_file.close()
        
        if db.export_to_excel(temp_filename):
            return send_file(temp_filename, 
                           as_attachment=True,
                           download_name=f'broadsens_database_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx',
                           mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        else:
            flash('Error exporting database!', 'error')
            return redirect(url_for('dashboard'))
    except Exception as e:
        flash(f'Export error: {str(e)}', 'error')
        return redirect(url_for('dashboard'))

@app.route('/export_order_sensors/<order_id>')
def export_order_sensors(order_id):
    # Check authentication first
    auth_check = require_login()
    if auth_check:
        return auth_check
    try:
        # Get order to include in filename
        order = db.get_order(order_id)
        if not order:
            flash('Order not found!', 'error')
            return redirect(url_for('orders'))
        
        # Create a temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
        temp_filename = temp_file.name
        temp_file.close()
        
        if db.export_order_sensors_to_excel(temp_filename, order_id):
            # Create a descriptive filename
            po_number = order.get('po_number', 'Unknown')
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f'order_sensors_PO_{po_number}_{timestamp}.xlsx'
            
            return send_file(temp_filename, 
                           as_attachment=True,
                           download_name=filename,
                           mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        else:
            flash('Error exporting order sensors!', 'error')
            return redirect(url_for('order_details', order_id=order_id))
    except Exception as e:
        flash(f'Export error: {str(e)}', 'error')
        return redirect(url_for('order_details', order_id=order_id))

if __name__ == '__main__':
    # For development only
    app.run(host='0.0.0.0', port=5000, debug=True)