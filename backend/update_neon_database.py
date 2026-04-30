#!/usr/bin/env python3
"""
Complete Neon database update script.
Runs migration and seeding for the new GPU integration.
"""

import os
import sys
import subprocess

# Set the database URL
os.environ["DATABASE_URL"] = "postgresql://neondb_owner:npg_L1cOxkJyS7mT@ep-billowing-shape-amibr6py-pooler.c-5.us-east-1.aws.neon.tech/neondb?channel_binding=require&sslmode=require"

def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"\n{'='*60}")
    print(f"🔄 {description}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=os.path.dirname(__file__))
        
        if result.returncode == 0:
            print(f"✅ {description} completed successfully")
            if result.stdout:
                print("Output:", result.stdout)
        else:
            print(f"❌ {description} failed")
            print("Error:", result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ Exception during {description}: {e}")
        return False
    
    return True

def main():
    """Run the complete database update process."""
    print("🚀 Neon Database Update for GPU Integration")
    print("=" * 60)
    print("Database: Neon PostgreSQL")
    print("Updates: New GPU schema + Hopper/Blackwell/RTX PRO data")
    
    # Step 1: Run Alembic migration
    migration_cmd = "python3 -m alembic upgrade head"
    if not run_command(migration_cmd, "Running Alembic migration (new GPU fields)"):
        print("❌ Migration failed. Please check the error above.")
        return False
    
    # Step 2: Run database seeding
    seeding_cmd = "python3 seed_database.py"
    if not run_command(seeding_cmd, "Seeding new GPU data"):
        print("❌ Seeding failed. Please check the error above.")
        return False
    
    # Step 3: Verification
    print(f"\n{'='*60}")
    print("🎯 Database Update Complete!")
    print(f"{'='*60}")
    print("✅ New GPU fields added to database schema")
    print("✅ 7 new GPU models seeded:")
    print("   • H100 SXM5, H200 SXM (Hopper)")
    print("   • B200 HGX, B300 HGX (Blackwell)")
    print("   • GB200 NVL72, GB300 NVL72 (Rack-scale)")
    print("   • RTX PRO 6000 BSE (Inference-only)")
    print("✅ Constraint filtering enabled")
    print("✅ VRAM math and concurrency calculations updated")
    print("\n🔄 Vercel will automatically redeploy with the new data")
    print("🌐 Your application should reflect the changes within minutes")
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        print("\n❌ Database update failed. Please check the errors above.")
        sys.exit(1)
    else:
        print("\n🎉 All done! Your GPU calculator is now updated with the latest NVIDIA GPUs.")
