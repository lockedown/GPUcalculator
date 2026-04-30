#!/usr/bin/env python3
"""
Database seeding script for Neon PostgreSQL instance.
Run this script to populate the database with the new GPU data.
"""

import os
import sys

# Set the database URL
os.environ["DATABASE_URL"] = "postgresql://neondb_owner:npg_L1cOxkJyS7mT@ep-billowing-shape-amibr6py-pooler.c-5.us-east-1.aws.neon.tech/neondb?channel_binding=require&sslmode=require"

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

try:
    from app.db.seed import run_seed
    
    print("Starting database seeding with new GPU data...")
    print("Database: Neon PostgreSQL")
    print("GPU Models to add: H100, H200, B200, B300, GB200, GB300, RTX PRO 6000 BSE")
    print()
    
    # Run the seed
    run_seed()
    
    print("\n✅ Database seeding completed successfully!")
    print("🎯 New GPU data is now available in the application")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're in the backend directory and dependencies are installed")
    sys.exit(1)
except Exception as e:
    print(f"❌ Seeding failed: {e}")
    sys.exit(1)
