#!/usr/bin/env python3
"""
Migration script to transfer data from JSON database to DynamoDB
"""

import json
import sys
from dynamodb_database import DynamoDBDatabase

def migrate_data():
    """Migrate data from JSON file to DynamoDB"""
    
    print("Starting migration from JSON to DynamoDB...")
    
    # Initialize DynamoDB connection
    try:
        ddb = DynamoDBDatabase()
        print("✓ Connected to DynamoDB successfully")
    except Exception as e:
        print(f"✗ Failed to connect to DynamoDB: {e}")
        return False
    
    # Load existing JSON data
    try:
        with open('sensor_database.json', 'r') as f:
            json_data = json.load(f)
        print("✓ Loaded existing JSON database")
    except FileNotFoundError:
        print("✗ sensor_database.json not found")
        return False
    except Exception as e:
        print(f"✗ Error loading JSON data: {e}")
        return False
    
    # Migrate customers
    print("\nMigrating customers...")
    customers_migrated = 0
    for customer in json_data.get('customers', []):
        try:
            # Use existing data structure, just change the method
            customer_data = {
                'name': customer['name'],
                'contact_person': customer['contact_person'],
                'email': customer['email'], 
                'phone': customer['phone'],
                'address': customer['address']
            }
            
            # Preserve original ID and created_at
            customer_data['id'] = customer['id']
            customer_data['created_at'] = customer['created_at']
            
            ddb.customers_table.put_item(Item=ddb._prepare_item(customer_data))
            customers_migrated += 1
        except Exception as e:
            print(f"  ✗ Failed to migrate customer {customer.get('id', 'unknown')}: {e}")
    
    print(f"✓ Migrated {customers_migrated} customers")
    
    # Migrate sites
    print("\nMigrating sites...")
    sites_migrated = 0
    for site in json_data.get('sites', []):
        try:
            site_data = {
                'customer_id': site['customer_id'],
                'name': site['name'],
                'location': site['location'],
                'contact_person': site['contact_person'],
                'phone': site['phone']
            }
            
            # Preserve original ID and created_at
            site_data['id'] = site['id']
            site_data['created_at'] = site['created_at']
            
            ddb.sites_table.put_item(Item=ddb._prepare_item(site_data))
            sites_migrated += 1
        except Exception as e:
            print(f"  ✗ Failed to migrate site {site.get('id', 'unknown')}: {e}")
    
    print(f"✓ Migrated {sites_migrated} sites")
    
    # Migrate orders
    print("\nMigrating orders...")
    orders_migrated = 0
    for order in json_data.get('orders', []):
        try:
            order_data = {
                'customer_id': order['customer_id'],
                'site_id': order['site_id'],
                'po_number': order['po_number'],
                'invoice_number': order.get('invoice_number', ''),
                'sensors': order['sensors'],
                'notes': order.get('notes', '')
            }
            
            # Preserve original ID and order_date
            order_data['id'] = order['id']
            order_data['order_date'] = order['order_date']
            
            ddb.orders_table.put_item(Item=ddb._prepare_item(order_data))
            orders_migrated += 1
        except Exception as e:
            print(f"  ✗ Failed to migrate order {order.get('id', 'unknown')}: {e}")
    
    print(f"✓ Migrated {orders_migrated} orders")
    
    # Migrate used IDs
    print("\nMigrating used sensor IDs...")
    used_ids_migrated = 0
    for used_id in json_data.get('used_ids', []):
        try:
            used_id_data = {
                'customer_id': used_id['customer_id'],
                'site_id': used_id['site_id'],
                'order_id': used_id['order_id'],
                'sensor_type': used_id['sensor_type'],
                'model': used_id['model'],
                'sensor_id': used_id['sensor_id'],
                'group_id': used_id['group_id'],
                'assigned_date': used_id['assigned_date'],
                'status': used_id['status']
            }
            
            # Preserve original ID
            used_id_data['id'] = used_id['id']
            
            ddb.used_ids_table.put_item(Item=ddb._prepare_item(used_id_data))
            used_ids_migrated += 1
        except Exception as e:
            print(f"  ✗ Failed to migrate used ID {used_id.get('id', 'unknown')}: {e}")
    
    print(f"✓ Migrated {used_ids_migrated} used sensor IDs")
    
    # Sensor types will be automatically loaded by ensure_sensor_types_loaded()
    print("\n✓ Sensor types will be automatically initialized")
    
    print(f"\n🎉 Migration completed successfully!")
    print(f"   - Customers: {customers_migrated}")
    print(f"   - Sites: {sites_migrated}")
    print(f"   - Orders: {orders_migrated}")
    print(f"   - Used IDs: {used_ids_migrated}")
    
    # Create backup of original JSON file
    import shutil
    backup_filename = f"sensor_database_backup_{int(__import__('time').time())}.json"
    shutil.copy('sensor_database.json', backup_filename)
    print(f"\n✓ Created backup: {backup_filename}")
    
    return True

if __name__ == "__main__":
    if migrate_data():
        print("\nMigration successful! You can now switch to DynamoDB.")
        sys.exit(0)
    else:
        print("\nMigration failed!")
        sys.exit(1)