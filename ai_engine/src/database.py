import mysql.connector
from mysql.connector import pooling
import logging
from config.settings import settings

logger = logging.getLogger("Database")


class DatabaseConnection:
    _pool = None

    @classmethod
    def get_pool(cls):
        if cls._pool is None:
            cls._pool = pooling.MySQLConnectionPool(
                pool_name="library_pool",
                pool_size=5,
                host=settings.DB_HOST,
                port=settings.DB_PORT,
                user=settings.DB_USER,
                password=settings.DB_PASSWORD,
                database=settings.DB_NAME,
                allow_public_key_retrieval=True,  # Fix for MySQL 8.0+
                autocommit=False
            )
            logger.info("Database connection pool created")
        return cls._pool

    @classmethod
    def get_connection(cls):
        pool = cls.get_pool()
        return pool.get_connection()


# Usage example
def get_db():
    return DatabaseConnection.get_connection()