# Neon Database Update Instructions

## Quick Update Method

Since the Python environment doesn't have the required dependencies, you can update your Neon database directly using the SQL script provided.

### Option 1: Neon Dashboard (Recommended)

1. **Go to Neon Console**: https://neon.tech/console
2. **Select your project**: `ep-billowing-shape-amibr6py`
3. **Go to SQL Editor**: Click "SQL" in the left sidebar
4. **Copy and paste** the contents of `backend/neon_update.sql`
5. **Run the script**: Click "Run" or press Cmd+Enter

### Option 2: psql Command Line

If you have psql installed:

```bash
psql "postgresql://neondb_owner:npg_L1cOxkJyS7mT@ep-billowing-shape-amibr6py-pooler.c-5.us-east-1.aws.neon.tech/neondb?channel_binding=require&sslmode=require" < backend/neon_update.sql
```

### Option 3: Using Neon CLI

```bash
# Install Neon CLI if needed
npm install -g neonctl

# Run the SQL script
neonctl sql --file backend/neon_update.sql
```

## What the Script Does

### 1. Schema Updates
- Adds new columns: `memory_gb`, `memory_type`, `supports_fp4`, `cooling_requirement`, `supported_workloads`
- Creates performance indexes
- Handles existing tables gracefully (checks if columns exist first)

### 2. Data Seeding
- **Clears existing GPU data** to ensure clean state
- **Inserts 8 new GPU models**:
  - H100 SXM5, H200 SXM (Hopper generation)
  - B100 HGX, B200 HGX, B300 HGX (Blackwell generation)  
  - GB200 NVL72, GB300 NVL72 (Rack-scale systems)
  - **RTX PRO 6000 BSE** (Inference-only, 96GB GDDR7)

### 3. Supporting Data
- Availability information for all GPUs
- Sample price history data
- Verification queries to confirm success

## After Running the Script

### Expected Results
You should see:
- **8 GPUs total** in the database
- **8 availability records**
- **Price history** for each GPU
- **RTX PRO 6000 BSE** with:
  - `memory_gb`: 96
  - `memory_type`: "GDDR7"
  - `supports_fp4`: true
  - `cooling_requirement`: "Air"
  - `supported_workloads`: ["inference"]

### Verification
The script ends with verification queries that show:
1. All GPU specifications
2. Total count of GPUs
3. Total count of availability records

## Next Steps

1. **Run the SQL script** using one of the methods above
2. **Check Vercel deployment** - it should auto-redeploy within minutes
3. **Test the application** - verify new GPUs appear and constraints work:
   - RTX PRO 6000 BSE should be filtered out for training workloads
   - B300 HGX should be filtered out for air-cooled environments
   - 200B models should be filtered for RTX PRO 6000 BSE

## Troubleshooting

### If the script fails:
- Check that you're connected to the correct database
- Ensure you have sufficient permissions
- Run sections of the script individually to isolate issues

### If data doesn't appear:
- Check the verification queries at the end of the script
- Ensure the INSERT statements completed successfully
- Refresh your Neon dashboard to see the updated tables

### If Vercel doesn't update:
- Check the Vercel dashboard for deployment status
- Verify the DATABASE_URL environment variable is correct
- Manually trigger a redeployment if needed

## Support

If you encounter any issues:
1. Check the Neon dashboard for any error messages
2. Verify the database connection string is correct
3. Ensure the SQL syntax is compatible with PostgreSQL
4. Contact support if database issues persist

The database update should complete within seconds, and your Vercel application will automatically reflect the new GPU data and constraint logic.
