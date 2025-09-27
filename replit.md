# Broadsens Order Management Tool

## Overview

This is a Flask-based web application for managing Broadsens sensor orders, customer information, site data, and automatic sensor ID assignments. The system handles the complete lifecycle of sensor order management including customer onboarding, site registration, order creation, and sensor ID assignment with automatic group ID generation. It serves as a comprehensive tool for tracking sensor deployments across multiple customer sites with built-in catalog management and export capabilities.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture
- **Framework**: Flask with Jinja2 templating engine for server-side rendering
- **UI Framework**: Bootstrap 5.3.0 with Font Awesome 6.0.0 icons for responsive design
- **Architecture Pattern**: Traditional multi-page application with server-rendered templates
- **Client-side Interactivity**: Minimal JavaScript for form interactions and dynamic dropdowns
- **Design System**: Custom CSS with BroadSens branding (#0066cc primary color)

### Backend Architecture
- **Framework**: Flask (Python) following MVC pattern with route-based controllers
- **Data Models**: Python dataclasses for type safety and structured data handling
- **Business Logic**: Centralized sensor catalog management with hardcoded Broadsens product specifications
- **Session Management**: Flask's built-in session handling with environment-configurable secret key
- **ID Generation Strategy**: Custom sequential sensor ID assignment with mathematical group ID mapping algorithm
- **Duplicate Prevention**: Per-site, per-sensor-type duplicate checking to prevent conflicts

### Data Storage Solutions
- **Primary Storage**: Amazon DynamoDB with automatic table creation and Global Secondary Indexes (GSIs)
- **Data Structure**: Five DynamoDB tables - customers, sites, orders, used_ids, and sensor_types with proper relationships
- **Cloud Persistence**: Data survives Replit republishing and deployment cycles via AWS cloud storage
- **ID Mapping**: External sensor mapping file for sensor ID to group ID correlations with cached lookup
- **Export Functionality**: Pandas integration for Excel export and data analysis from DynamoDB
- **Scalability**: Enterprise-grade AWS DynamoDB backend supports virtually unlimited growth
- **Fallback System**: Graceful fallback to JSON file system if DynamoDB connection fails

### Core Business Logic
- **Sensor Catalog Management**: Hardcoded Broadsens product catalog with multiple sensor types (SVT-A, SVT-V, etc.)
- **Automatic ID Assignment**: Sequential numbering system with corresponding group ID generation
- **Order Lifecycle**: Complete order management from creation through fulfillment tracking
- **Site-Customer Relationship**: Hierarchical data model supporting multiple sites per customer
- **PO/Invoice Tracking**: Purchase order and invoice number management for financial tracking

### Authentication and Authorization
- **Security Model**: Basic session-based security without user authentication
- **Access Control**: Single-user administrative interface with no role-based permissions
- **Data Validation**: Server-side form validation for all user inputs and business rule enforcement

## External Dependencies

### Third-Party Libraries
- **Flask**: Core web framework providing routing, templating, and request handling
- **boto3**: AWS SDK for Python enabling DynamoDB database operations and cloud storage
- **pandas**: Data manipulation library for Excel export functionality and data analysis
- **Bootstrap**: Frontend CSS framework hosted via CDN for responsive UI components
- **Font Awesome**: Icon library hosted via CDN for enhanced user interface elements

### External Services
- **Amazon DynamoDB**: Primary cloud database service for persistent data storage
- **AWS Infrastructure**: Leverages AWS credentials and region configuration for secure cloud access
- **CDN Dependencies**: Bootstrap and Font Awesome served from external CDNs
- **No Authentication Services**: No external authentication providers or services integrated

### Recent Changes
- **September 2025**: Successfully migrated from JSON file database to Amazon DynamoDB for enterprise-grade data persistence that survives republishing and deployment cycles