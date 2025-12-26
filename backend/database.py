import mysql.connector
from mysql.connector import Error, pooling
import bcrypt
from datetime import datetime
import json
from contextlib import contextmanager

# MySQL Configuration for XAMPP
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',  # Default XAMPP MySQL password is empty
    'database': 'loan_prediction_db',
    'port': 3307
}

# Create connection pool
connection_pool = None

def init_connection_pool():
    """Initialize MySQL connection pool"""
    global connection_pool
    try:
        connection_pool = pooling.MySQLConnectionPool(
            pool_name="loan_pool",
            pool_size=5,
            pool_reset_session=True,
            **DB_CONFIG
        )
        print(" MySQL connection pool created successfully!")
    except Error as e:
        print(f" Error creating connection pool: {e}")

@contextmanager
def get_db():
    """Context manager for database connections"""
    if connection_pool is None:
        init_connection_pool()
    
    conn = connection_pool.get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        yield cursor
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def create_database():
    """Create database if it doesn't exist"""
    try:
        conn = mysql.connector.connect(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            port=DB_CONFIG['port']
        )
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']}")
        cursor.close()
        conn.close()
        print(f" Database '{DB_CONFIG['database']}' is ready!")
    except Error as e:
        print(f" Error creating database: {e}")
        raise e

def init_db():
    """Initialize database tables"""
    # First, ensure database exists
    create_database()
    
    # Now create tables
    with get_db() as cursor:
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                hashed_password VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_username (username),
                INDEX idx_email (email)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Predictions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS predictions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                name VARCHAR(255),
                annual_income DECIMAL(15, 2),
                debt_to_income_ratio DECIMAL(5, 4),
                credit_score DECIMAL(5, 2),
                loan_amount DECIMAL(15, 2),
                interest_rate DECIMAL(5, 2),
                gender VARCHAR(50),
                marital_status VARCHAR(50),
                education_level VARCHAR(100),
                employment_status VARCHAR(100),
                loan_purpose VARCHAR(100),
                grade_subgrade VARCHAR(10),
                prediction TINYINT NOT NULL,
                probability DECIMAL(5, 4) NOT NULL,
                prediction_type VARCHAR(20) NOT NULL,
                batch_id VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                INDEX idx_user_id (user_id),
                INDEX idx_batch_id (batch_id),
                INDEX idx_created_at (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        print("✅ Database tables initialized successfully!")

# User functions
def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_user(username: str, email: str, password: str) -> dict:
    """Create a new user"""
    hashed_pw = hash_password(password)
    
    with get_db() as cursor:
        cursor.execute(
            'INSERT INTO users (username, email, hashed_password) VALUES (%s, %s, %s)',
            (username, email, hashed_pw)
        )
        user_id = cursor.lastrowid
        
        return {
            "id": user_id,
            "username": username,
            "email": email,
            "hashed_password": hashed_pw
        }

def get_user_by_username(username: str) -> dict:
    """Get user by username"""
    with get_db() as cursor:
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        row = cursor.fetchone()
        return row

def get_user_by_email(email: str) -> dict:
    """Get user by email"""
    with get_db() as cursor:
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        row = cursor.fetchone()
        return row

# Prediction functions
def create_prediction(user_id: int, loan_data: dict, prediction: int, 
                     probability: float, prediction_type: str, batch_id: str = None) -> dict:
    """Create a new prediction record"""
    with get_db() as cursor:
        cursor.execute('''
            INSERT INTO predictions (
                user_id, name, annual_income, debt_to_income_ratio, 
                credit_score, loan_amount, interest_rate, gender, 
                marital_status, education_level, employment_status, 
                loan_purpose, grade_subgrade, prediction, probability, 
                prediction_type, batch_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            user_id,
            loan_data.get("name"),
            loan_data.get("annual_income"),
            loan_data.get("debt_to_income_ratio"),
            loan_data.get("credit_score"),
            loan_data.get("loan_amount"),
            loan_data.get("interest_rate"),
            loan_data.get("gender"),
            loan_data.get("marital_status"),
            loan_data.get("education_level"),
            loan_data.get("employment_status"),
            loan_data.get("loan_purpose"),
            loan_data.get("grade_subgrade"),
            prediction,
            probability,
            prediction_type,
            batch_id
        ))
        
        prediction_id = cursor.lastrowid
        
        # Get the created prediction
        cursor.execute('SELECT * FROM predictions WHERE id = %s', (prediction_id,))
        row = cursor.fetchone()
        
        # Convert datetime to string for JSON serialization
        if row and 'created_at' in row:
            row['created_at'] = row['created_at'].isoformat()
        
        return row

def get_user_predictions(user_id: int) -> list:
    """Get all predictions for a user"""
    with get_db() as cursor:
        cursor.execute(
            'SELECT * FROM predictions WHERE user_id = %s ORDER BY created_at DESC',
            (user_id,)
        )
        rows = cursor.fetchall()
        
        # Convert datetime objects to strings
        for row in rows:
            if 'created_at' in row and row['created_at']:
                row['created_at'] = row['created_at'].isoformat()
            # Convert Decimal to float for JSON serialization
            for key in ['annual_income', 'debt_to_income_ratio', 'credit_score', 
                       'loan_amount', 'interest_rate', 'probability']:
                if key in row and row[key] is not None:
                    row[key] = float(row[key])
        
        return rows

def get_prediction_by_id(prediction_id: int) -> dict:
    """Get a single prediction by ID"""
    with get_db() as cursor:
        cursor.execute('SELECT * FROM predictions WHERE id = %s', (prediction_id,))
        row = cursor.fetchone()
        
        if row and 'created_at' in row:
            row['created_at'] = row['created_at'].isoformat()
        
        return row

def get_batch_predictions(batch_id: str) -> list:
    """Get all predictions from a batch"""
    with get_db() as cursor:
        cursor.execute(
            'SELECT * FROM predictions WHERE batch_id = %s ORDER BY created_at',
            (batch_id,)
        )
        rows = cursor.fetchall()
        
        for row in rows:
            if 'created_at' in row and row['created_at']:
                row['created_at'] = row['created_at'].isoformat()
        
        return rows

# Initialize database when module is imported
if __name__ != "__main__":
    try:
        init_db()
    except Exception as e:
        print(f"⚠️  Database initialization warning: {e}")
        print("⚠️  Make sure XAMPP MySQL is running!")
else:
    # If run directly, test the database connection
    print("=" * 60)
    print(" Testing Loan Prediction Database Connection")
    print("=" * 60)
    
    try:
        # Test database creation and connection
        init_db()
        
        print("\n SUCCESS! Database is working properly!")
        print("\n Database Information:")
        print(f"   Host: {DB_CONFIG['host']}")
        print(f"   Database: {DB_CONFIG['database']}")
        print(f"   Port: {DB_CONFIG['port']}")
        
        # Check tables
        with get_db() as cursor:
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            print(f"\n Tables found: {len(tables)}")
            for table in tables:
                table_name = list(table.values())[0]
                cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
                count = cursor.fetchone()['count']
                print(f"   - {table_name}: {count} records")
        
        print("\n" + "=" * 60)
        print(" Database test completed successfully!")
        print("=" * 60)
        
    except Error as e:
        print("\n DATABASE CONNECTION FAILED!")
        print(f"Error: {e}")
        print("\n  Troubleshooting Steps:")
        print("   1. Make sure XAMPP MySQL is running (green in control panel)")
        print("   2. Check MySQL is on port 3306")
        print("   3. Verify MySQL password is correct in database.py")
        print("   4. Try opening phpMyAdmin to test MySQL")
        print("=" * 60)