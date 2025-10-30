"""
Quick test script to verify database connection
Run this before starting your Streamlit app
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment
load_dotenv("key.env")

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ DATABASE_URL not found in key.env")
    exit(1)

print(f"📋 Testing connection to: {DATABASE_URL.split('@')[1].split('/')[0]}")  # Show host only
print()

try:
    # Create engine
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    
    # Test connection
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version()"))
        version = result.fetchone()[0]
        print("✅ Database connection successful!")
        print(f"📊 PostgreSQL version: {version[:50]}...")
        print()
        
        # Test if employees table exists
        result = conn.execute(text("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_name = 'employees'
        """))
        table_exists = result.fetchone()[0]
        
        if table_exists:
            print("✅ 'employees' table found")
            
            # Get row count
            result = conn.execute(text("SELECT COUNT(*) FROM employees"))
            count = result.fetchone()[0]
            print(f"📈 Total employees: {count}")
        else:
            print("⚠️  'employees' table not found")
            
except Exception as e:
    print(f"❌ Connection failed: {e}")
    print()
    print("💡 Troubleshooting steps:")
    print("1. Go to Supabase Dashboard → Project Settings → Database")
    print("2. Copy the Connection String (URI format)")
    print("3. Replace DATABASE_URL in key.env with the exact string")
    print("4. Make sure you've replaced [YOUR-PASSWORD] with your actual password")