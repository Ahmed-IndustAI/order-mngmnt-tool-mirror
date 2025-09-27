import boto3
from boto3.dynamodb.conditions import Key, Attr
import json
import os
import uuid
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Any
import pandas as pd
from decimal import Decimal
from werkzeug.security import generate_password_hash

# AWS DynamoDB setup - will be initialized in DynamoDBDatabase class

# Data Models (same as original)
@dataclass
class User:
    id: str
    email: str
    password_hash: str
    created_at: str

@dataclass
class SensorType:
    type_code: str
    name: str
    description: str
    models: List[str]

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
class Order:
    id: str
    customer_id: str
    site_id: str
    po_number: str
    invoice_number: str
    sensors: List[Dict]
    notes: str
    order_date: str

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

class DynamoDBDatabase:
    def __init__(self):
        self.table_prefix = "broadsens"
        
        # Initialize DynamoDB with proper error handling
        try:
            self.dynamodb = boto3.resource(
                'dynamodb',
                aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
                aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
                region_name=os.environ['AWS_REGION']
            )
            # Test connection by listing tables
            list(self.dynamodb.tables.limit(1))
            print("✓ DynamoDB connection successful")
        except Exception as e:
            print(f"✗ Failed to connect to DynamoDB: {e}")
            raise
            
        self.customers_table = None
        self.sites_table = None
        self.orders_table = None
        self.used_ids_table = None
        self.sensor_types_table = None
        self.users_table = None
        self.user_tokens_table = None
        self.allowed_emails_table = None
        
        # Load sensor mapping
        self.sid_to_gid = {}
        self._load_sensor_mapping()
        
        # Initialize tables
        self._initialize_tables()
        
        # Ensure sensor types are loaded
        self.ensure_sensor_types_loaded()
        
        # Initialize allowed emails
        self.initialize_allowed_emails()

    def _initialize_tables(self):
        """Create DynamoDB tables if they don't exist"""
        try:
            # Customers table
            self.customers_table = self.dynamodb.Table(f'{self.table_prefix}_customers')
            self.customers_table.load()
        except Exception:
            self._create_customers_table()
            
        try:
            # Sites table
            self.sites_table = self.dynamodb.Table(f'{self.table_prefix}_sites')
            self.sites_table.load()
        except Exception:
            self._create_sites_table()
            
        try:
            # Orders table
            self.orders_table = self.dynamodb.Table(f'{self.table_prefix}_orders')
            self.orders_table.load()
        except Exception:
            self._create_orders_table()
            
        try:
            # Used IDs table
            self.used_ids_table = self.dynamodb.Table(f'{self.table_prefix}_used_ids')
            self.used_ids_table.load()
        except Exception:
            self._create_used_ids_table()
            
        try:
            # Sensor Types table
            self.sensor_types_table = self.dynamodb.Table(f'{self.table_prefix}_sensor_types')
            self.sensor_types_table.load()
        except Exception:
            self._create_sensor_types_table()
            
        try:
            # Users table
            self.users_table = self.dynamodb.Table(f'{self.table_prefix}_users')
            self.users_table.load()
        except Exception:
            self._create_users_table()
            
        try:
            # User Tokens table
            self.user_tokens_table = self.dynamodb.Table(f'{self.table_prefix}_user_tokens')
            self.user_tokens_table.load()
        except Exception:
            self._create_user_tokens_table()
            
        try:
            # Allowed emails table
            self.allowed_emails_table = self.dynamodb.Table(f'{self.table_prefix}_allowed_emails')
            self.allowed_emails_table.load()
        except Exception:
            self._create_allowed_emails_table()
            
        print("✓ All DynamoDB tables initialized successfully")

    def _create_customers_table(self):
        """Create customers table"""
        self.customers_table = self.dynamodb.create_table(
            TableName=f'{self.table_prefix}_customers',
            KeySchema=[
                {'AttributeName': 'id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'id', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        self.customers_table.wait_until_exists()

    def _create_sites_table(self):
        """Create sites table"""
        self.sites_table = self.dynamodb.create_table(
            TableName=f'{self.table_prefix}_sites',
            KeySchema=[
                {'AttributeName': 'id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'id', 'AttributeType': 'S'},
                {'AttributeName': 'customer_id', 'AttributeType': 'S'}
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'customer_id-index',
                    'KeySchema': [
                        {'AttributeName': 'customer_id', 'KeyType': 'HASH'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'}
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        self.sites_table.wait_until_exists()

    def _create_orders_table(self):
        """Create orders table"""
        self.orders_table = self.dynamodb.create_table(
            TableName=f'{self.table_prefix}_orders',
            KeySchema=[
                {'AttributeName': 'id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'id', 'AttributeType': 'S'},
                {'AttributeName': 'customer_id', 'AttributeType': 'S'},
                {'AttributeName': 'site_id', 'AttributeType': 'S'}
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'customer_id-index',
                    'KeySchema': [
                        {'AttributeName': 'customer_id', 'KeyType': 'HASH'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'}
                },
                {
                    'IndexName': 'site_id-index',
                    'KeySchema': [
                        {'AttributeName': 'site_id', 'KeyType': 'HASH'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'}
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        self.orders_table.wait_until_exists()

    def _create_used_ids_table(self):
        """Create used IDs table"""
        self.used_ids_table = self.dynamodb.create_table(
            TableName=f'{self.table_prefix}_used_ids',
            KeySchema=[
                {'AttributeName': 'id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'id', 'AttributeType': 'S'},
                {'AttributeName': 'order_id', 'AttributeType': 'S'},
                {'AttributeName': 'site_id', 'AttributeType': 'S'}
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'order_id-index',
                    'KeySchema': [
                        {'AttributeName': 'order_id', 'KeyType': 'HASH'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'}
                },
                {
                    'IndexName': 'site_id-index',
                    'KeySchema': [
                        {'AttributeName': 'site_id', 'KeyType': 'HASH'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'}
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        self.used_ids_table.wait_until_exists()

    def _create_sensor_types_table(self):
        """Create sensor types table"""
        self.sensor_types_table = self.dynamodb.create_table(
            TableName=f'{self.table_prefix}_sensor_types',
            KeySchema=[
                {'AttributeName': 'type_code', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'type_code', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        self.sensor_types_table.wait_until_exists()

    def _create_users_table(self):
        """Create users table"""
        self.users_table = self.dynamodb.create_table(
            TableName=f'{self.table_prefix}_users',
            KeySchema=[
                {'AttributeName': 'id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'id', 'AttributeType': 'S'},
                {'AttributeName': 'email', 'AttributeType': 'S'}
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'email-index',
                    'KeySchema': [
                        {'AttributeName': 'email', 'KeyType': 'HASH'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'}
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        self.users_table.wait_until_exists()

    def _create_user_tokens_table(self):
        """Create user tokens table"""
        self.user_tokens_table = self.dynamodb.create_table(
            TableName=f'{self.table_prefix}_user_tokens',
            KeySchema=[
                {'AttributeName': 'token', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'token', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        self.user_tokens_table.wait_until_exists()

    def _create_allowed_emails_table(self):
        """Create allowed emails table"""
        self.allowed_emails_table = self.dynamodb.create_table(
            TableName=f'{self.table_prefix}_allowed_emails',
            KeySchema=[
                {'AttributeName': 'email', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'email', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        self.allowed_emails_table.wait_until_exists()

    def _load_sensor_mapping(self):
        """Load sensor ID to group ID mapping from file"""
        try:
            with open('sensor_mapping.txt', 'r') as f:
                for line in f:
                    if line.strip() and not line.startswith('#'):
                        # Format: "for sid 1, the gid = 01"
                        if 'for sid' in line and 'gid =' in line:
                            parts = line.split('for sid')[1].split(',')[0].strip()
                            gid_part = line.split('gid =')[1].strip()
                            try:
                                sid = int(parts)
                                gid = gid_part
                                self.sid_to_gid[sid] = gid
                            except ValueError:
                                continue
        except FileNotFoundError:
            print("Warning: sensor_mapping.txt not found")

    def _convert_decimals(self, obj):
        """Convert DynamoDB Decimal objects to int/float for JSON serialization"""
        if isinstance(obj, list):
            return [self._convert_decimals(item) for item in obj]
        elif isinstance(obj, dict):
            return {key: self._convert_decimals(value) for key, value in obj.items()}
        elif isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        else:
            return obj

    def _prepare_item(self, item):
        """Prepare item for DynamoDB by converting problematic types"""
        if isinstance(item, dict):
            result = {}
            for key, value in item.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    result[key] = Decimal(str(value))
                elif isinstance(value, list):
                    result[key] = [self._prepare_item(v) if isinstance(v, dict) else v for v in value]
                elif isinstance(value, dict):
                    result[key] = self._prepare_item(value)
                else:
                    result[key] = value
            return result
        return item

    # CRUD Operations for Customers
    def add_customer(self, customer_data):
        customer = Customer(
            id=str(uuid.uuid4()),
            created_at=datetime.now().isoformat(),
            **customer_data
        )
        
        item = self._prepare_item(asdict(customer))
        self.customers_table.put_item(Item=item)
        return customer.id

    def update_customer(self, customer_id, customer_data):
        customer_data['id'] = customer_id
        
        # Get existing customer to preserve created_at
        existing = self.get_customer(customer_id)
        if existing:
            customer_data['created_at'] = existing.get('created_at', datetime.now().isoformat())
            
        item = self._prepare_item(customer_data)
        self.customers_table.put_item(Item=item)
        return True

    def get_customer(self, customer_id):
        response = self.customers_table.get_item(Key={'id': customer_id})
        if 'Item' in response:
            return self._convert_decimals(response['Item'])
        return None

    def get_customers(self):
        response = self.customers_table.scan()
        return self._convert_decimals(response['Items'])

    # CRUD Operations for Sites
    def add_site(self, site_data):
        site = Site(
            id=str(uuid.uuid4()),
            created_at=datetime.now().isoformat(),
            **site_data
        )
        
        item = self._prepare_item(asdict(site))
        self.sites_table.put_item(Item=item)
        return site.id

    def update_site(self, site_id, site_data):
        site_data['id'] = site_id
        
        # Get existing site to preserve created_at
        existing = self.get_site(site_id)
        if existing:
            site_data['created_at'] = existing.get('created_at', datetime.now().isoformat())
            
        item = self._prepare_item(site_data)
        self.sites_table.put_item(Item=item)
        return True

    def get_site(self, site_id):
        response = self.sites_table.get_item(Key={'id': site_id})
        if 'Item' in response:
            return self._convert_decimals(response['Item'])
        return None

    def get_sites(self, customer_id=None):
        if customer_id:
            response = self.sites_table.query(
                IndexName='customer_id-index',
                KeyConditionExpression=Key('customer_id').eq(customer_id)
            )
            return self._convert_decimals(response['Items'])
        else:
            response = self.sites_table.scan()
            return self._convert_decimals(response['Items'])

    # CRUD Operations for Orders
    def add_order(self, order_data):
        order = Order(
            id=str(uuid.uuid4()),
            order_date=datetime.now().isoformat(),
            **order_data
        )
        
        item = self._prepare_item(asdict(order))
        self.orders_table.put_item(Item=item)
        
        # Always assign sensor IDs
        self._assign_sensor_ids(order.id, order.site_id, order.customer_id, order.sensors)
        
        return order.id

    def update_order(self, order_id, order_data):
        order_data['id'] = order_id
        
        # Get existing order to preserve order_date
        existing = self.get_order(order_id)
        if existing:
            order_data['order_date'] = existing.get('order_date', datetime.now().isoformat())
            
            # If sensors changed, reassign IDs
            old_sensors = existing.get('sensors', [])
            new_sensors = order_data.get('sensors', [])
            
            if old_sensors != new_sensors:
                # Remove old sensor IDs for this order
                self._remove_sensor_ids_for_order(order_id)
                # Assign new sensor IDs
                self._assign_sensor_ids(order_id, order_data['site_id'], order_data['customer_id'], new_sensors)
        
        item = self._prepare_item(order_data)
        self.orders_table.put_item(Item=item)
        return True

    def get_order(self, order_id):
        response = self.orders_table.get_item(Key={'id': order_id})
        if 'Item' in response:
            return self._convert_decimals(response['Item'])
        return None

    def get_orders(self, customer_id=None, site_id=None):
        if customer_id:
            response = self.orders_table.query(
                IndexName='customer_id-index',
                KeyConditionExpression=Key('customer_id').eq(customer_id)
            )
            orders = self._convert_decimals(response['Items'])
        elif site_id:
            response = self.orders_table.query(
                IndexName='site_id-index',
                KeyConditionExpression=Key('site_id').eq(site_id)
            )
            orders = self._convert_decimals(response['Items'])
        else:
            response = self.orders_table.scan()
            orders = self._convert_decimals(response['Items'])
        
        # Sort by order_date (most recent first)
        if isinstance(orders, list):
            return sorted(orders, key=lambda x: x.get('order_date', '') if isinstance(x, dict) else '', reverse=True)
        return []

    def is_po_number_duplicate(self, customer_id, site_id, po_number, exclude_order_id=None):
        """Check if PO number already exists for the same customer-site combination"""
        orders = self.get_orders(customer_id=customer_id)
        for order in orders:
            if (order['site_id'] == site_id and 
                order['po_number'] == po_number and 
                order['id'] != exclude_order_id):
                return True
        return False

    # Sensor ID Management
    def _assign_sensor_ids(self, order_id, site_id, customer_id, sensors):
        """Assign sensor IDs for an order"""
        for item in sensors:
            sensor_type = item['sensor_type']
            model = item['model']
            quantity = item['quantity']

            # Get used sensor IDs for this site and sensor type
            used_sids = self.get_used_sensor_ids_for_site_type(site_id, sensor_type)

            for i in range(quantity):
                # Find next available sensor ID (start from 1, not 0)
                sid = 1
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

                    item = self._prepare_item(asdict(used_id))
                    self.used_ids_table.put_item(Item=item)
                    used_sids.add(sid)

    def _remove_sensor_ids_for_order(self, order_id):
        """Remove all sensor IDs assigned to an order"""
        response = self.used_ids_table.query(
            IndexName='order_id-index',
            KeyConditionExpression=Key('order_id').eq(order_id)
        )
        
        for item in response['Items']:
            self.used_ids_table.delete_item(Key={'id': item['id']})

    def get_used_sensor_ids_for_site_type(self, site_id, sensor_type):
        """Get all used sensor IDs for a specific site and sensor type"""
        response = self.used_ids_table.query(
            IndexName='site_id-index',
            KeyConditionExpression=Key('site_id').eq(site_id),
            FilterExpression=Attr('sensor_type').eq(sensor_type)
        )
        
        return {int(item['sensor_id']) for item in response['Items']}

    def get_used_ids_for_order(self, order_id):
        """Get all used IDs for a specific order"""
        response = self.used_ids_table.query(
            IndexName='order_id-index',
            KeyConditionExpression=Key('order_id').eq(order_id)
        )
        
        return self._convert_decimals(response['Items'])

    def get_used_ids(self, site_id=None, sensor_type=None, customer_id=None):
        """Get used IDs with optional filtering by site_id, sensor_type, and customer_id"""
        try:
            # If filtering by site_id, use the site_id index for efficiency
            if site_id:
                response = self.used_ids_table.query(
                    IndexName='site_id-index',
                    KeyConditionExpression=Key('site_id').eq(site_id)
                )
                used_ids = self._convert_decimals(response['Items'])
            else:
                # Otherwise, scan the entire table
                response = self.used_ids_table.scan()
                used_ids = self._convert_decimals(response['Items'])
            
            # Apply additional filters
            if customer_id:
                used_ids = [u for u in used_ids if u.get('customer_id') == customer_id]
            if sensor_type:
                used_ids = [u for u in used_ids if u.get('sensor_type') == sensor_type]
            
            # Sort by sensor_id numerically to maintain consistent order
            used_ids.sort(key=lambda x: int(x.get('sensor_id', 0)))
                
            return used_ids
        except Exception as e:
            print(f"Error getting used IDs: {e}")
            return []

    def get_all_used_ids(self):
        """Get all used sensor IDs"""
        response = self.used_ids_table.scan()
        return self._convert_decimals(response['Items'])

    # Sensor Types Management
    def ensure_sensor_types_loaded(self):
        """Ensure BroadSens sensor types are loaded in database"""
        from app import BROADSENS_SENSOR_CATALOG
        
        response = self.sensor_types_table.scan()
        if not response.get('Items', []):
            # Initialize sensor types with BroadSens catalog
            for type_code, info in BROADSENS_SENSOR_CATALOG.items():
                sensor_type = SensorType(
                    type_code=type_code,
                    name=info['name'],
                    description=info['description'],
                    models=info['models']
                )
                item = self._prepare_item(asdict(sensor_type))
                self.sensor_types_table.put_item(Item=item)

    def get_sensor_types(self):
        """Get all sensor types"""
        response = self.sensor_types_table.scan()
        return self._convert_decimals(response['Items'])

    # Statistics
    def get_statistics(self):
        """Get dashboard statistics"""
        customers_response = self.customers_table.scan(Select='COUNT')
        sites_response = self.sites_table.scan(Select='COUNT')
        orders_response = self.orders_table.scan(Select='COUNT')
        used_ids_response = self.used_ids_table.scan(Select='COUNT')
        
        return {
            'total_customers': customers_response['Count'],
            'total_sites': sites_response['Count'],
            'total_orders': orders_response['Count'],
            'total_sensors_assigned': used_ids_response['Count']
        }

    # Export functionality
    def export_to_excel(self, filename):
        """Export database to Excel file with multiple sheets"""
        try:
            with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
                # Customers sheet
                customers_df = pd.DataFrame(self.get_customers())
                customers_df.to_excel(writer, sheet_name='Customers', index=False)

                # Sites sheet  
                sites_df = pd.DataFrame(self.get_sites())
                sites_df.to_excel(writer, sheet_name='Sites', index=False)

                # Orders sheet
                orders_df = pd.DataFrame(self.get_orders())
                orders_df.to_excel(writer, sheet_name='Orders', index=False)

                # Used IDs sheet
                used_ids_df = pd.DataFrame(self.get_all_used_ids())
                used_ids_df.to_excel(writer, sheet_name='Sensor_IDs', index=False)

                # Sensor Types sheet
                sensor_types_df = pd.DataFrame(self.get_sensor_types())
                sensor_types_df.to_excel(writer, sheet_name='Sensor_Types', index=False)

            return True
        except Exception as e:
            print(f"Error exporting to Excel: {e}")
            return False

    def export_order_sensors_to_excel(self, filename, order_id):
        """Export sensor data for a specific order to Excel file"""
        try:
            # Get sensor data for this order only
            order_sensors = self.get_used_ids_for_order(order_id)
            
            # Create simplified dataframe with only the required columns
            if order_sensors:
                sensors_df = pd.DataFrame(order_sensors)
                # Select only the columns we want: sensor_id, group_id, sensor_type, model
                columns_to_export = ['sensor_id', 'group_id', 'sensor_type', 'model']
                sensors_df = sensors_df[columns_to_export]
                
                # Rename columns for better readability
                sensors_df.columns = ['Sensor ID', 'Group ID', 'Sensor Type', 'Model']
                
                with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
                    sensors_df.to_excel(writer, sheet_name='Order_Sensors', index=False)
            else:
                # Create empty DataFrame if no sensors
                empty_df = pd.DataFrame([], columns=['Sensor ID', 'Group ID', 'Sensor Type', 'Model'])
                with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
                    empty_df.to_excel(writer, sheet_name='Order_Sensors', index=False)
                    
            return True
        except Exception as e:
            print(f"Error exporting order sensors to Excel: {e}")
            return False

    # User Authentication Methods
    def get_user_by_email(self, email):
        """Get user by email address"""
        email = email.lower().strip()  # Normalize email for lookup
        try:
            response = self.users_table.query(
                IndexName='email-index',
                KeyConditionExpression=Key('email').eq(email)
            )
            items = response.get('Items', [])
            if items:
                user_data = self._convert_decimals(items[0])
                # Import User class from app module
                from app import User
                return User(user_data['id'], user_data['email'], user_data['password_hash'])
            return None
        except Exception as e:
            print(f"Error getting user by email: {e}")
            return None

    def get_user_by_id(self, user_id):
        """Get user by ID"""
        try:
            response = self.users_table.get_item(Key={'id': user_id})
            if 'Item' in response:
                user_data = self._convert_decimals(response['Item'])
                # Import User class from app module
                from app import User
                return User(user_data['id'], user_data['email'], user_data['password_hash'])
            return None
        except Exception as e:
            print(f"Error getting user by ID: {e}")
            return None
            
    def create_user(self, email, password):
        """Create a new user"""
        email = email.lower().strip()  # Normalize email for storage
        
        # Check if user already exists
        if self.get_user_by_email(email):
            return None
        
        # Import User class from app module
        from app import User
        
        # Create new user
        user = User.create_user(email, password)
        user_data = {
            'id': user.id,
            'email': email,  # Store normalized email
            'password_hash': user.password_hash,
            'created_at': datetime.now().isoformat()
        }
        
        try:
            item = self._prepare_item(user_data)
            self.users_table.put_item(Item=item)
            return user
        except Exception as e:
            print(f"Error creating user: {e}")
            return None

    # User Token Methods (for compatibility with existing auth system)
    def get_user_tokens(self):
        """Get all user tokens - compatibility method"""
        try:
            response = self.user_tokens_table.scan()
            tokens_dict = {}
            for item in response.get('Items', []):
                item = self._convert_decimals(item)
                tokens_dict[item['token']] = {
                    'user_id': item['user_id'],
                    'user_email': item['user_email'],
                    'created_at': item['created_at']
                }
            return tokens_dict
        except Exception as e:
            print(f"Error getting user tokens: {e}")
            return {}
    
    def save_user_token(self, token, user_id, user_email):
        """Save a user token"""
        try:
            token_data = {
                'token': token,
                'user_id': user_id,
                'user_email': user_email,
                'created_at': datetime.now().isoformat()
            }
            item = self._prepare_item(token_data)
            self.user_tokens_table.put_item(Item=item)
            return True
        except Exception as e:
            print(f"Error saving user token: {e}")
            return False
    
    def delete_user_token(self, token):
        """Delete a user token"""
        try:
            self.user_tokens_table.delete_item(Key={'token': token})
            return True
        except Exception as e:
            print(f"Error deleting user token: {e}")
            return False
    
    def get_user_token(self, token):
        """Get a specific user token"""
        try:
            response = self.user_tokens_table.get_item(Key={'token': token})
            if 'Item' in response:
                item = self._convert_decimals(response['Item'])
                return {
                    'user_id': item['user_id'],
                    'user_email': item['user_email'],
                    'created_at': item['created_at']
                }
            return None
        except Exception as e:
            print(f"Error getting user token: {e}")
            return None

    # Compatibility property for existing code
    @property
    def data(self):
        """Compatibility property to mimic the original JSON database structure"""
        return {
            'user_tokens': self.get_user_tokens()
        }
    
    def _save_database(self):
        """Compatibility method - DynamoDB auto-saves so this is a no-op"""
        pass
    
    # Allowed Emails Management
    def is_email_allowed(self, email):
        """Check if email is allowed for registration"""
        try:
            email = email.lower().strip()
            response = self.allowed_emails_table.get_item(Key={'email': email})
            return 'Item' in response
        except Exception as e:
            print(f"Error checking allowed email: {e}")
            return False
    
    def add_allowed_email(self, email):
        """Add an email to the allowed list"""
        try:
            email = email.lower().strip()
            self.allowed_emails_table.put_item(Item={'email': email})
            return True
        except Exception as e:
            print(f"Error adding allowed email: {e}")
            return False
    
    def remove_allowed_email(self, email):
        """Remove an email from the allowed list"""
        try:
            email = email.lower().strip()
            self.allowed_emails_table.delete_item(Key={'email': email})
            return True
        except Exception as e:
            print(f"Error removing allowed email: {e}")
            return False
    
    def get_allowed_emails(self):
        """Get all allowed emails"""
        try:
            response = self.allowed_emails_table.scan()
            return [item['email'] for item in response['Items']]
        except Exception as e:
            print(f"Error getting allowed emails: {e}")
            return []
    
    def initialize_allowed_emails(self):
        """Initialize allowed emails table with default emails"""
        default_emails = [
            "a.ahmed@industrai.eu",
            "marouane@industrai.eu", 
            "tareq@industrai.eu",
            "yousri@industrai.eu"
        ]
        
        # Check if table is empty first
        try:
            response = self.allowed_emails_table.scan(Limit=1)
            if response['Count'] == 0:
                # Table is empty, add default emails
                for email in default_emails:
                    self.add_allowed_email(email)
                print(f"✓ Initialized {len(default_emails)} allowed emails")
        except Exception as e:
            print(f"Error initializing allowed emails: {e}")