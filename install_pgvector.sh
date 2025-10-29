#!/bin/bash
# Install pgvector extension for PostgreSQL

echo "Installing pgvector extension..."

# Update package list
sudo apt update

# Install pgvector for PostgreSQL 14
sudo apt install -y postgresql-14-pgvector

# Restart PostgreSQL
sudo systemctl restart postgresql

# Enable the extension in the database
PGPASSWORD=your_secure_db_password_here psql -U neo_druidic_user -d neo_druidic -h localhost -c "CREATE EXTENSION IF NOT EXISTS vector;"

echo "✅ pgvector installed successfully!"
echo "You can verify with: PGPASSWORD=your_secure_db_password_here psql -U neo_druidic_user -d neo_druidic -h localhost -c \"SELECT * FROM pg_extension WHERE extname = 'vector';\""
