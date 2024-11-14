from fastapi import APIRouter, HTTPException, Request
import json
import redis.asyncio as redis
import os
import redis.asyncio as redis
from dotenv import load_dotenv
from app.services.chromadb_services import del_chromadb_collection

load_dotenv()

redis_url = os.getenv("REDIS_URL")
redis_db = int(os.getenv("REDIS_DB"))

redis_client = redis.from_url(redis_url, db=redis_db)

router = APIRouter()

# this is called wehn the app is uninstalled 
@router.delete("/delete")
async def delete_sync_data(request: Request):
    try:
        data = await request.json()
        shop_name = data.get("shop_name")

        if not shop_name:
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        # removing the store form the queue if it is in queue
        queue = await redis_client.lrange('sync_queue1', 0, -1)
        data_to_remove = json.dumps({"shop_name": shop_name})    #converts to json string

        await redis_client.lrem('sync_queue1', 0, data_to_remove)

        return {"message": f"Successfully removed entries for shop_name: {shop_name}"}

        raise HTTPException(status_code=404, detail=f"shop_name: {shop_name} not found in the queue")

    except HTTPException as e:
        raise e
    
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


