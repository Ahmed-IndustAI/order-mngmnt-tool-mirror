
"""
BroadSens Sensor Management Tool
================================
A comprehensive web-based tool for managing BroadSens sensor orders,
customer information, site data, and automatic sensor ID assignments.

Features:
- Customer and Site Management
- BroadSens Sensor Catalog Management  
- Order Creation and Tracking
- Automatic Sensor ID and Group ID Assignment
- Duplicate Prevention (per sensor type per site)
- PO/Invoice Tracking
- Excel Database Export
- Usage Analytics

Updated with actual BroadSens product catalog.
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
import json
import os
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
import uuid
import pandas as pd
import re


app = Flask(__name__)
app.secret_key = os.environ.get('SESSION_SECRET', 'broadsens-sensor-management-2024')

# BroadSens Sensor Catalog - Updated with actual products
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
    status: str
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

# Database Class
class SensorDatabase:
    def __init__(self, db_file='sensor_database.json'):
        self.db_file = db_file
        self.data = self._load_database()

        # Load sensor ID to group ID mapping
        self.sid_to_gid = self._load_sensor_mapping()

    def _load_sensor_mapping(self):
        """Load the sensor ID to group ID mapping from file"""
        mapping_file = 'sensor_mapping.txt'
        sid_to_gid = {}

        if os.path.exists(mapping_file):
            with open(mapping_file, 'r') as f:
                content = f.read()

            lines = content.strip().split('\n')
            for line in lines:
                line = line.strip()
                if line and 'sid' in line and 'gid' in line:
                    match = re.search(r'for sid (\d+), the gid = ([0-9A-Za-z]+)', line)
                    if match:
                        sid = int(match.group(1))
                        gid = match.group(2)
                        sid_to_gid[sid] = gid

        return sid_to_gid

    def _load_database(self):
        """Load database from JSON file"""
        if os.path.exists(self.db_file):
            with open(self.db_file, 'r') as f:
                return json.load(f)
        else:
            return {
                'customers': [],
                'sites': [],
                'sensor_types': [],
                'orders': [],
                'used_ids': []
            }

    def _save_database(self):
        """Save database to JSON file"""
        with open(self.db_file, 'w') as f:
            json.dump(self.data, f, indent=2, default=str)

    def initialize_sample_data(self):
        """Initialize database with sample data if empty"""
        if not self.data['customers']:
            # Initialize sensor types with BroadSens catalog
            for type_code, info in BROADSENS_SENSOR_CATALOG.items():
                sensor_type = SensorType(
                    type_code=type_code,
                    name=info['name'],
                    description=info['description'],
                    models=info['models']
                )
                self.data['sensor_types'].append(asdict(sensor_type))

            # Sample customers
            customers = [
                Customer("cust001", "Acme Manufacturing", "John Smith", "john@acme.com", "+1-555-0101", "123 Industrial Ave, Detroit, MI", datetime.now().isoformat()),
                Customer("cust002", "TechCorp Industries", "Sarah Johnson", "sarah@techcorp.com", "+1-555-0102", "456 Tech Park Blvd, Austin, TX", datetime.now().isoformat()),
                Customer("cust003", "Global Dynamics", "Mike Chen", "mike@globaldynamics.com", "+1-555-0103", "789 Corporate Dr, San Jose, CA", datetime.now().isoformat())
            ]

            # Sample sites
            sites = [
                Site("site001", "cust001", "Acme Plant A", "Detroit Main Facility", "Bob Wilson", "+1-555-0201", datetime.now().isoformat()),
                Site("site002", "cust001", "Acme Plant B", "Detroit Secondary Facility", "Alice Brown", "+1-555-0202", datetime.now().isoformat()),
                Site("site003", "cust002", "TechCorp HQ", "Austin Headquarters", "David Lee", "+1-555-0203", datetime.now().isoformat()),
                Site("site004", "cust003", "Global Dynamics West", "San Jose Main Plant", "Lisa Wang", "+1-555-0204", datetime.now().isoformat())
            ]

            # Sample orders
            orders = [
                Order("ord001", "cust001", "site001", "PO-2024-001", "INV-2024-001", datetime.now().isoformat(), 
                     "Active", [{"sensor_type": "SVT-A", "model": "SVT200-A", "quantity": 50}], "Initial sensor deployment"),
                Order("ord002", "cust002", "site003", "PO-2024-002", "INV-2024-002", datetime.now().isoformat(), 
                     "Active", [{"sensor_type": "SVT-V", "model": "SVT300-V", "quantity": 25}], "Velocity monitoring setup"),
                Order("ord003", "cust003", "site004", "PO-2024-003", "", datetime.now().isoformat(), 
                     "Pending", [{"sensor_type": "SVT-T", "model": "SVT200-T", "quantity": 15}], "High temperature monitoring")
            ]

            # Add data to database
            self.data['customers'] = [asdict(c) for c in customers]
            self.data['sites'] = [asdict(s) for s in sites]
            self.data['orders'] = [asdict(o) for o in orders]

            # Generate some sample used IDs for the first two orders
            for order in orders[:2]:  # Only for "Active" orders
                self._assign_sensor_ids(order.id, order.site_id, order.customer_id, order.sensors)

            self._save_database()

    def _assign_sensor_ids(self, order_id, site_id, customer_id, sensors):
        """Assign sensor IDs for an order"""
        for item in sensors:
            sensor_type = item['sensor_type']
            model = item['model']
            quantity = item['quantity']

            # Get next available sensor IDs for this site and sensor type
            used_sids = self.get_used_sensor_ids_for_site_type(site_id, sensor_type)

            for i in range(quantity):
                # Find next available sensor ID
                sid = 0
                while sid in used_sids or sid >= len(self.sid_to_gid):
                    sid += 1

                if sid < len(self.sid_to_gid):
                    gid = self.sid_to_gid[sid]

                    # Create UsedID record
                    used_id = UsedID(
                        id=str(uuid.uuid4()),
                        customer_id=customer_id,
                        site_id=site_id,
                        order_id=order_id,
                        sensor_type=sensor_type,
                        model=model,
                        sensor_id=sid,
                        group_id=gid,
                        assigned_date=datetime.now().isoformat(),
                        status="Assigned"
                    )

                    self.data['used_ids'].append(asdict(used_id))
                    used_sids.add(sid)

    # CRUD Operations
    def add_customer(self, customer_data):
        customer = Customer(
            id=str(uuid.uuid4()),
            created_at=datetime.now().isoformat(),
            **customer_data
        )
        self.data['customers'].append(asdict(customer))
        self._save_database()
        return customer.id

    def add_site(self, site_data):
        site = Site(
            id=str(uuid.uuid4()),
            created_at=datetime.now().isoformat(),
            **site_data
        )
        self.data['sites'].append(asdict(site))
        self._save_database()
        return site.id

    def add_order(self, order_data):
        order = Order(
            id=str(uuid.uuid4()),
            order_date=datetime.now().isoformat(),
            **order_data
        )
        self.data['orders'].append(asdict(order))

        # Always assign sensor IDs for all orders
        self._assign_sensor_ids(order.id, order.site_id, order.customer_id, order.sensors)

        self._save_database()
        return order.id

    def get_customers(self):
        return self.data['customers']

    def get_sites(self, customer_id=None):
        if customer_id:
            return [s for s in self.data['sites'] if s['customer_id'] == customer_id]
        return self.data['sites']

    def get_orders(self, customer_id=None, site_id=None):
        orders = self.data['orders']
        if customer_id:
            orders = [o for o in orders if o['customer_id'] == customer_id]
        if site_id:
            orders = [o for o in orders if o['site_id'] == site_id]
        return orders

    def get_sensor_types(self):
        return self.data['sensor_types']

    def get_used_ids(self, site_id=None, sensor_type=None):
        used_ids = self.data['used_ids']
        if site_id:
            used_ids = [u for u in used_ids if u['site_id'] == site_id]
        if sensor_type:
            used_ids = [u for u in used_ids if u['sensor_type'] == sensor_type]
        return used_ids

    def get_used_sensor_ids_for_site_type(self, site_id, sensor_type):
        """Get set of used sensor IDs for a specific site and sensor type"""
        used_ids = self.get_used_ids(site_id, sensor_type)
        return {u['sensor_id'] for u in used_ids}

    def get_site_capacity_info(self, site_id):
        """Get capacity information for all sensor types at a site"""
        capacity_info = {}

        for sensor_type_data in self.data['sensor_types']:
            sensor_type = sensor_type_data['type_code']
            used_count = len(self.get_used_ids(site_id, sensor_type))
            available = 3844 - used_count

            capacity_info[sensor_type] = {
                'used': used_count,
                'available': available,
                'total': 3844,
                'percentage': round((used_count / 3844) * 100, 1)
            }

        return capacity_info

    def export_to_excel(self, filename):
        """Export database to Excel file with multiple sheets"""
        try:
            with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
                # Customers sheet
                customers_df = pd.DataFrame(self.data['customers'])
                customers_df.to_excel(writer, sheet_name='Customers', index=False)

                # Sites sheet  
                sites_df = pd.DataFrame(self.data['sites'])
                sites_df.to_excel(writer, sheet_name='Sites', index=False)

                # Orders sheet
                orders_df = pd.DataFrame(self.data['orders'])
                orders_df.to_excel(writer, sheet_name='Orders', index=False)

                # Used IDs sheet
                used_ids_df = pd.DataFrame(self.data['used_ids'])
                used_ids_df.to_excel(writer, sheet_name='Used_IDs', index=False)

                # Sensor Types sheet
                sensor_types_df = pd.DataFrame(self.data['sensor_types'])
                sensor_types_df.to_excel(writer, sheet_name='Sensor_Types', index=False)

            return True
        except Exception as e:
            print(f"Excel export error: {e}")
            return False

# Initialize database
db = SensorDatabase()
#db.initialize_sample_data()

# Flask Routes
@app.route('/')
def dashboard():
    customers = db.get_customers()
    sites = db.get_sites()
    orders = db.get_orders()
    sensor_types = db.get_sensor_types()

    stats = {
        'total_customers': len(customers),
        'total_sites': len(sites),
        'total_orders': len(orders),
        'total_sensor_types': len(sensor_types),
        'total_assigned_sensors': len(db.get_used_ids())
    }

    return render_template('dashboard.html', 
                         customers=customers[:5], 
                         recent_orders=orders[-5:], 
                         stats=stats)

@app.route('/customers')
def customers():
    customers = db.get_customers()
    return render_template('customers.html', customers=customers)

@app.route('/add_customer', methods=['GET', 'POST'])
def add_customer():
    if request.method == 'POST':
        customer_data = {
            'name': request.form['name'],
            'contact_person': request.form['contact_person'],
            'email': request.form['email'],
            'phone': request.form['phone'],
            'address': request.form['address']
        }
        customer_id = db.add_customer(customer_data)
        flash(f'Customer added successfully! ID: {customer_id}', 'success')
        return redirect(url_for('customers'))

    return render_template('add_customer.html')

@app.route('/sites')
def sites():
    sites = db.get_sites()
    customers = db.get_customers()

    # Add customer names to sites
    customer_dict = {c['id']: c['name'] for c in customers}
    for site in sites:
        site['customer_name'] = customer_dict.get(site['customer_id'], 'Unknown')

    return render_template('sites.html', sites=sites, customers=customers)

@app.route('/add_site', methods=['GET', 'POST'])
def add_site():
    customers = db.get_customers()

    if request.method == 'POST':
        site_data = {
            'customer_id': request.form['customer_id'],
            'name': request.form['name'],
            'location': request.form['location'],
            'contact_person': request.form['contact_person'],
            'phone': request.form['phone']
        }
        site_id = db.add_site(site_data)
        flash(f'Site added successfully! ID: {site_id}', 'success')
        return redirect(url_for('sites'))

    return render_template('add_site.html', customers=customers)

@app.route('/orders')
def orders():
    orders = db.get_orders()
    customers = db.get_customers()
    sites = db.get_sites()

    # Add customer and site names to orders
    customer_dict = {c['id']: c['name'] for c in customers}
    site_dict = {s['id']: s['name'] for s in sites}

    for order in orders:
        order['customer_name'] = customer_dict.get(order['customer_id'], 'Unknown')
        order['site_name'] = site_dict.get(order['site_id'], 'Unknown')

    return render_template('orders.html', orders=orders)

@app.route('/create_order', methods=['GET', 'POST'])
def create_order():
    customers = db.get_customers()
    sensor_types = db.get_sensor_types()

    if request.method == 'POST':
        # Parse sensors from form
        sensors = []
        sensor_type = request.form.get('sensor_type')
        model = request.form.get('model')
        quantity = int(request.form.get('quantity', 0))

        if sensor_type and model and quantity > 0:
            sensors.append({
                'sensor_type': sensor_type,
                'model': model,
                'quantity': quantity
            })

        order_data = {
            'customer_id': request.form['customer_id'],
            'site_id': request.form['site_id'],
            'po_number': request.form['po_number'],
            'invoice_number': request.form['invoice_number'],
            'status': 'Active',  # All orders are now treated as active
            'sensors': sensors,
            'notes': request.form['notes']
        }

        order_id = db.add_order(order_data)
        flash(f'Order created successfully! ID: {order_id}', 'success')
        return redirect(url_for('orders'))

    return render_template('create_order.html', customers=customers, sensor_types=sensor_types)

@app.route('/get_sites/<customer_id>')
def get_sites_for_customer(customer_id):
    sites = db.get_sites(customer_id)
    return jsonify(sites)

@app.route('/get_models/<sensor_type>')
def get_models_for_sensor_type(sensor_type):
    sensor_types = db.get_sensor_types()
    for st in sensor_types:
        if st['type_code'] == sensor_type:
            return jsonify(st['models'])
    return jsonify([])

@app.route('/sensor_types')
def sensor_types():
    sensor_types = db.get_sensor_types()
    return render_template('sensor_types.html', sensor_types=sensor_types)

@app.route('/used_ids')
def used_ids():
    used_ids = db.get_used_ids()
    customers = db.get_customers()
    sites = db.get_sites()

    # Add customer and site names
    customer_dict = {c['id']: c['name'] for c in customers}
    site_dict = {s['id']: s['name'] for s in sites}

    for uid in used_ids:
        uid['customer_name'] = customer_dict.get(uid['customer_id'], 'Unknown')
        uid['site_name'] = site_dict.get(uid['site_id'], 'Unknown')

    return render_template('used_ids.html', used_ids=used_ids)

@app.route('/order/<order_id>')
def order_details(order_id):
    orders = db.get_orders()
    order = next((o for o in orders if o['id'] == order_id), None)

    if not order:
        flash('Order not found', 'error')
        return redirect(url_for('orders'))

    # Get related data
    customers = db.get_customers()
    sites = db.get_sites()
    used_ids = [uid for uid in db.get_used_ids() if uid['order_id'] == order_id]

    customer = next((c for c in customers if c['id'] == order['customer_id']), None)
    site = next((s for s in sites if s['id'] == order['site_id']), None)

    return render_template('order_details.html', 
                         order=order, 
                         customer=customer, 
                         site=site, 
                         used_ids=used_ids)

@app.route('/export_excel')
def export_excel():
    filename = f'sensor_database_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    filepath = os.path.join('static', filename)

    # Create static directory if it doesn't exist
    os.makedirs('static', exist_ok=True)

    if db.export_to_excel(filepath):
        return send_file(filepath, as_attachment=True, download_name=filename)
    else:
        flash('Export failed', 'error')
        return redirect(url_for('dashboard'))


if __name__ == "__main__":
    print("Starting BroadSens Sensor Management Tool...")
    print("Server will be available on port 5000")
    print("\nBroadSens Sensor Catalog:")
    for sensor_type, info in BROADSENS_SENSOR_CATALOG.items():
        print(f"- {sensor_type}: {len(info['models'])} models")
    print(f"\nTotal: {len(BROADSENS_SENSOR_CATALOG)} sensor types, {sum(len(info['models']) for info in BROADSENS_SENSOR_CATALOG.values())} models")
    print("✓ 3844 limit applies per SENSOR TYPE per site (not per model)")
    
    # Initialize sample data
    db.initialize_sample_data()
    
    app.run(host="0.0.0.0", port=5000, debug=True)
