"""
MySQL Sync Test Suite with Logging
Tests database connection, sync process, and data integrity.
"""

import sys
import os
import logging
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import get_db
from src.mysql.sync_data import sync_to_mysql
from config.settings import settings
from config.logging_config import setup_logging, get_logger

# Setup logging
setup_logging("test_mysql_sync", log_to_file=True)
logger = get_logger("MySQLSyncTest")


def test_docker_running():
    """Test 1: Docker container is running"""
    logger.info("="*60)
    logger.info("TEST 1: Docker Container Status")
    logger.info("="*60)
    
    import subprocess
    try:
        result = subprocess.run(
            ['docker', 'ps', '--filter', 'name=mysql_db', '--format', '{{.Names}}: {{.Status}}'],
            capture_output=True,
            text=True,
            check=True
        )
        
        if 'mysql_db' in result.stdout:
            logger.info(f"✓ Docker container running: {result.stdout.strip()}")
            return True
        else:
            logger.error("✗ MySQL container not found")
            return False
    except Exception as e:
        logger.error(f"✗ Docker check failed: {e}")
        return False


def test_database_connection():
    """Test 2: Database connection"""
    logger.info("\n" + "="*60)
    logger.info("TEST 2: Database Connection")
    logger.info("="*60)
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()
        cursor.close()
        conn.close()
        
        logger.info(f"✓ Connected to MySQL: {version[0]}")
        return True
    except Exception as e:
        logger.error(f"✗ Connection failed: {e}")
        return False


def test_processed_data_exists():
    """Test 3: Processed data files exist"""
    logger.info("\n" + "="*60)
    logger.info("TEST 3: Processed Data Files")
    logger.info("="*60)
    
    import glob
    pattern = os.path.join(settings.DATA_PROCESSED_DIR, "clean_books_*.json")
    files = glob.glob(pattern)
    
    if files:
        logger.info(f"✓ Found {len(files)} processed file(s)")
        for f in files:
            logger.info(f"  - {os.path.basename(f)}")
        return True
    else:
        logger.warning("✗ No processed files found")
        logger.info("  Run 'python main.py process' first")
        return False


def test_database_tables():
    """Test 4: Database tables exist"""
    logger.info("\n" + "="*60)
    logger.info("TEST 4: Database Tables")
    logger.info("="*60)
    
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        
        # Check tables
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        table_names = [list(t.values())[0] for t in tables]
        
        required_tables = ['books', 'publishers', 'categories', 'authors', 
                          'book_categories', 'book_authors', 'shelves']
        
        missing = [t for t in required_tables if t not in table_names]
        
        if not missing:
            logger.info(f"✓ All required tables exist ({len(table_names)} total)")
            return True
        else:
            logger.error(f"✗ Missing tables: {missing}")
            return False
            
    except Exception as e:
        logger.error(f"✗ Table check failed: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def test_data_counts():
    """Test 5: Check data counts in database"""
    logger.info("\n" + "="*60)
    logger.info("TEST 5: Database Statistics")
    logger.info("="*60)
    
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                (SELECT COUNT(*) FROM books) as books,
                (SELECT COUNT(*) FROM publishers) as publishers,
                (SELECT COUNT(*) FROM categories) as categories,
                (SELECT COUNT(*) FROM authors) as authors
        """)
        
        stats = cursor.fetchone()
        
        logger.info("✓ Database statistics:")
        logger.info(f"  Books:      {stats['books']}")
        logger.info(f"  Publishers: {stats['publishers']}")
        logger.info(f"  Categories: {stats['categories']}")
        logger.info(f"  Authors:    {stats['authors']}")
        
        return stats['books'] > 0
        
    except Exception as e:
        logger.error(f"✗ Statistics check failed: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def test_relationships():
    """Test 6: Check N-N relationships"""
    logger.info("\n" + "="*60)
    logger.info("TEST 6: Data Relationships")
    logger.info("="*60)
    
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        
        # Check book-category links
        cursor.execute("SELECT COUNT(*) as count FROM book_categories")
        bc_count = cursor.fetchone()['count']
        
        # Check book-author links
        cursor.execute("SELECT COUNT(*) as count FROM book_authors")
        ba_count = cursor.fetchone()['count']
        
        logger.info(f"✓ Book-Category links: {bc_count}")
        logger.info(f"✓ Book-Author links: {ba_count}")
        
        return bc_count > 0 and ba_count > 0
        
    except Exception as e:
        logger.error(f"✗ Relationship check failed: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def run_all_tests():
    """Run all tests"""
    logger.info("\n" + "#"*60)
    logger.info("# MySQL SYNC TEST SUITE")
    logger.info("#"*60)
    logger.info(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("#"*60 + "\n")
    
    tests = [
        test_docker_running,
        test_database_connection,
        test_processed_data_exists,
        test_database_tables,
        test_data_counts,
        test_relationships
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append((test.__name__, result))
        except Exception as e:
            logger.error(f"Test {test.__name__} crashed: {e}")
            results.append((test.__name__, False))
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("TEST SUMMARY")
    logger.info("="*60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{status} - {name}")
    
    logger.info("="*60)
    logger.info(f"Results: {passed}/{total} tests passed")
    logger.info("="*60)
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
