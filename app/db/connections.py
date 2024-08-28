import aiomysql
from fastapi import HTTPException
from app.config import DB_NAME, DB_USER, DB_PASS, DB_HOST

from dotenv import load_dotenv
import os
load_dotenv()

db_name = os.getenv('db')
db_user = os.getenv('user')
db_pass = os.getenv('password')
db_host = os.getenv('host')

# print(db_name)
# print(db_user)
# print(db_pass)
# print(db_host)

async def get_db_connection():
    try:
        pool = await aiomysql.create_pool(
            host=db_host,
            user=db_user,
            password=db_pass,
            db=db_name,
            autocommit=True
        )
        return pool
    except Exception as e:
        print(f"Database connection error: {e}")
        raise HTTPException(status_code=500, detail="Failed to connect to the database")
