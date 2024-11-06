from fastapi import APIRouter, HTTPException, Request
import json
import redis.asyncio as redis
import os
from dotenv import load_dotenv
import aiomysql
from app.db.connections import get_db_connection
from app.services.chromadb_services import del_chromadb_collection


load_dotenv()

redis_url = os.getenv("REDIS_URL")
redis_db = int(os.getenv("REDIS_DB"))
redis_client = redis.from_url(redis_url, db=redis_db)

router = APIRouter()

async def get_shop_id(cursor, shop_name):
    """Get the shop id based on shop name."""
    sql = "SELECT id FROM shop_table WHERE shop_name = %s"
    await cursor.execute(sql, (shop_name,))
    result = await cursor.fetchone()
    if result is None:
        return None
    return result[0]

async def delete_sync_time(cursor, shop_id):
    """Delete the sync_time row based on shop id."""
    sql = "DELETE FROM sync_time WHERE shop_id = %s"
    await cursor.execute(sql, (shop_id,))

@router.delete("/deleteTime")
async def delete_sync_data(request: Request):
    try:
        data = await request.json()
        shop_name = data.get("shop_name")

        if not shop_name:
            raise HTTPException(status_code=400, detail="Missing required fields")

        pool = await get_db_connection()

        async with pool.acquire() as connection:
            async with connection.cursor() as cursor:
                shop_id = await get_shop_id(cursor, shop_name)
                print(shop_id)
                if shop_id is None:
                    raise HTTPException(status_code=404, detail=f"Shop name: {shop_name} not found")

                await delete_sync_time(cursor, shop_id)
                await connection.commit()

        del_chromadb_collection(shop_name)

        data_to_remove = json.dumps({"shop_name": shop_name})
        await redis_client.lrem('sync_queue1', 0, data_to_remove)

        return {"message": f"Successfully removed entries for shop_name: {shop_name}"}

    except HTTPException as e:
        raise e

    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")
