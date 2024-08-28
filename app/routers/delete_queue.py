#shopname in request
#check redis queue and remvoe from there
#chromadb me se remove
# ye sab bhi threadpool me ho and not on main thread ?
 
from fastapi import APIRouter, HTTPException, Request
import json
import redis.asyncio as redis
import os
import redis.asyncio as redis
from dotenv import load_dotenv

load_dotenv()

redis_url = os.getenv("REDIS_URL")
redis_db = int(os.getenv("REDIS_DB"))

redis_client = redis.from_url(redis_url, db=redis_db)

router = APIRouter()

@router.delete("/sync")
async def delete_sync_data(request: Request):
    try:
        data = await request.json()
        shop_name = data.get("shop_name")

        if not shop_name:
            raise HTTPException(status_code=400, detail="Missing required fields")

        queue = await redis_client.lrange('sync_queue', 0, -1)
        
        for item in queue:
            item_data = json.loads(item)
            if item_data.get("shop_name") == shop_name:
                await redis_client.lrem('sync_queue', 0, item)
                return {"status": "success", "detail": f"Removed shop_name: {shop_name}"}

        raise HTTPException(status_code=404, detail=f"shop_name: {shop_name} not found in the queue")

    except HTTPException as e:
        raise e
    
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


