#!/usr/bin/env python3
"""
Database initialization script.
Creates all tables and sets up the database schema.
"""

from app.database.database import create_tables
from app.database.models import Base
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Initialize the database."""
    try:
        logger.info("Creating database tables...")
        create_tables()
        logger.info("Database tables created successfully!")
        
        # Print table information
        logger.info("Created tables:")
        for table_name in Base.metadata.tables.keys():
            logger.info(f"  - {table_name}")
            
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise

if __name__ == "__main__":
    main()
    main()
