from fastapi import APIRouter, HTTPException, Request , BackgroundTasks
import aiomysql
from app.db.connections import get_db_connection
from app.services.chromadb_services import get_chromadb_collection
from app.services.model_service import get_embeddings   #get_embeddings_and_predictions 
import requests
import httpx
import asyncio
import numpy as np
import time
from PIL import Image
from io import BytesIO
import tempfile
from datetime import datetime
from fastapi.concurrency import run_in_threadpool
# import redis
import json
import redis.asyncio as redis
import os
import redis.asyncio as redis
from dotenv import load_dotenv

load_dotenv()

redis_url = os.getenv("REDIS_URL")
redis_db = int(os.getenv("REDIS_DB"))

router = APIRouter()

redis_client = redis.from_url(redis_url, db=redis_db)

redis_client = redis.from_url("redis://localhost:6379", db=0)
# redis = redis.Redis(host='localhost', port=6379, db=0)
processing = False



# all the functions being used in the sync api have been written here
# these functioon can later be put in different folders to followe FastApis folder structure



# function which gets all the shopify products
async def fetch_shopify_products(shop_token: str):
    api_url = 'https://siar-development.myshopify.com/admin/api/2024-01/products.json?fields=id,image,title,handle,variants&limit=250'
    headers = {'X-Shopify-Access-Token': shop_token}
    
    all_products = []  # List 
    
    async with httpx.AsyncClient() as client:
        while api_url:
            try:
                response = await client.get(api_url, headers=headers)
                response.raise_for_status()
                data = response.json()
                products = data.get('products', [])

                print (products) 
                
                for product in products:
                    product_id = product.get('id')
                    image = product.get('image')
                    title =product.get('title')
                    handle = product.get('handle')
                    price = product['variants'][0].get('price')
                    # price=variants.get('price')
                    image_src = image.get('src') if image else None
                    if product_id and image_src:
                        all_products.append({'id': product_id, 'image_src': image_src , 'title':title, 'handle':handle, 'price':price })
# all_products.append({'id': product_id, 'image_src': image_src , 'title':title , 'price':price, 'handle':handle})


                # Pagination handling
                link_header = response.headers.get('Link', '')
                next_url = None
                if 'rel="next"' in link_header:
                    parts = link_header.split(',')
                    for part in parts:
                        if 'rel="next"' in part:
                            next_url = part.split(';')[0].strip('<> ')
                            break
                api_url = next_url
            
            except httpx.HTTPStatusError as http_err:
                print(f"HTTP error occurred: {http_err}")
            except Exception as err:
                print(f"An error occurred: {err}")

    # print(f"Total products fetched: {len(all_products)}")
    # print("Fetched Products Data:", all_products)
    return all_products


#we get the shop id from the database, if it doesnt exist then it is created
async def get_or_create_shop_id(cursor, shop_name):
    try:
        # Check if the shop exists
        sql = "SELECT id FROM shop_table WHERE shop_name = %s"
        await cursor.execute(sql, (shop_name,))
        result = await cursor.fetchone()
        if result:
            return result[0]
        else:
            # If the shop does not exist
            sql = "INSERT INTO shop_table (shop_name) VALUES (%s)"
            await cursor.execute(sql, (shop_name,))
            await cursor.execute("SELECT LAST_INSERT_ID()")
            result = await cursor.fetchone()
            if result:
                return result[0]
            else:
                raise HTTPException(status_code=500, detail="Failed to create shop")
    except aiomysql.Error as e:
        print(f"Select or insert data error: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


#we get the shop tokn from the database
async def get_shop_token(cursor, shop_name):
    try:
        sql = "SELECT accessToken FROM shopify_sessions WHERE shop = %s"
        await cursor.execute(sql, (shop_name,))
        result = await cursor.fetchone()
        return result[0]
    except aiomysql.Error as e:
        raise HTTPException(status_code=500, detail="An unexpected error occurred")



#after the products have been synced for a shop the sync time is saved , can be later shown to the user if needed 
async def insert_sync_time(cursor, sync_time, shop_id):
    try:
        select_sql = "SELECT 1 FROM sync_time WHERE shop_id = %s"
        await cursor.execute(select_sql, (shop_id,))
        result = await cursor.fetchone()

        if result:
            update_sql = "UPDATE sync_time SET time = %s WHERE shop_id = %s"
            await cursor.execute(update_sql, (sync_time, shop_id))
        else:
            insert_sql = "INSERT INTO sync_time (time, shop_id) VALUES (%s, %s)"
            await cursor.execute(insert_sql, (sync_time, shop_id))
    except aiomysql.Error as e:
        print(f"Insert data error: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")



#function to insert data into chromadb
def upsert_to_chromadb(collection, product_id, embeddings,metadatas, title):
    collection.upsert(
        ids=[str(product_id)], 
        embeddings=[embeddings], 
        metadatas=[metadatas],
        documents=[title]
    )


#calls all the function and gets products from shopfy to storing them in the chromadb, this is done in the abckground and not on the main thread
async def process_products():
    global processing 
    processing = True
    try:
        while processing:
            item = await redis_client.lindex('sync_queue', 0)
            if not item:
                processing = False
                break

            data = json.loads(item)
            print(data)
            shop_name = data.get("shop_name")
            #shop_token = data.get("shop_token")
            print(shop_name)
            #print(shop_token)

            try:
                pool = await get_db_connection()
                async with pool.acquire() as connection:
                    async with connection.cursor() as cursor:
                        shop_id = await get_or_create_shop_id(cursor, shop_name)
                        print(shop_id)

                pool.close()
                await pool.wait_closed()

            except Exception as e:
                print(f"Error fetching or creating shop_id: {e}")
                continue

            try:
                pool = await get_db_connection()
                async with pool.acquire() as connection:
                    async with connection.cursor() as cursor:
                        shop_token = await get_shop_token(cursor, shop_name)

                pool.close()
                await pool.wait_closed()

            except Exception as e:
                print(f"Error fetching or creating shop_id: {e}")
                continue


            products = await fetch_shopify_products(shop_token)
            collection = get_chromadb_collection(shop_name)

            for index, product in enumerate(products):
                product_id = product['id']
                image_src = product['image_src']
                title = product['title']
                price = product['price']
                handle = product['handle']

                metadata = {
                'price': price,
                'handle': handle,
                'image_src':image_src
                }
               

                try:
                    # Download and open the image asynchronously
                    img_response = await run_in_threadpool(requests.get, image_src)
                    if img_response.status_code != 200:
                        raise ValueError(f"Failed to download image, status code: {img_response.status_code}")

                    try:
                        img = Image.open(BytesIO(img_response.content))
                    except Exception as e:
                        raise ValueError(f"Error opening image: {e}")

                    img = img.resize((299, 299))
                    start_time = time.time()
                    embeddings = await run_in_threadpool(get_embeddings, img) 
                    #embeddings,top_categories = await run_in_threadpool(get_embeddings_and_predictions, img)  #approach didint work
                    await run_in_threadpool(upsert_to_chromadb, collection, product_id, embeddings,metadata, title) 
                    #await run_in_threadpool(upsert_to_chromadb, collection, product_id, embeddings,metadata, top_categories)   #approach didnt work

                    end_time = time.time()
                    embedding_time = end_time - start_time
                    print(f"Time from image download to saving in ChromaDB for product {product_id}: {embedding_time:.2f} seconds")

                    print(f"Processed {index + 1}/{len(products)} products. Remaining: {len(products) - (index + 1)}")

                except Exception as e:
                    print(f"Error processing image for product {product_id} at {image_src}: {e}")

            try:
                pool = await get_db_connection()
                async with pool.acquire() as connection:
                    async with connection.cursor() as cursor:
                        now = datetime.now().isoformat()  # Get the current time in ISO format
                        await insert_sync_time(cursor, now, shop_id)

                pool.close()
                await pool.wait_closed()

            except Exception as e:
                print(f"Error inserting sync time: {e}")

            # Remove the processed item from the queue
            await redis_client.lpop('sync_queue')

    except Exception as e:
        print(f"Error processing queue: {e}")

    finally:
        processing = False




#the router
@router.post("/sync")
async def sync_data(request: Request, background_tasks: BackgroundTasks):
    global processing
    try:
        data = await request.json()
        shop_name = data.get("shop_name")
        # shop_token = data.get("shop_token")

        if not shop_name: # or not shop_token:
            raise HTTPException(status_code=400, detail="Missing required fields")

    
        data = {
        "shop_name": shop_name #,
        # "shop_token": shop_token
        }

        data_json = json.dumps(data)
        await redis_client.rpush('sync_queue', data_json)

        if processing == False:
            processing = True
            background_tasks.add_task(process_products)

        return {"status": "success"}

    except HTTPException as e:
        raise e
    
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")
    



















# old functions below of no use now




# with queue implmented but only once 
# async def process_products():
#     try:
#             item = await redis_client.lindex('my_queue', 0)
#             if item:
#                 data = json.loads(item)
#                 print(data)
#                 shop_name= data.get("shop_name")
#                 shop_token= data.get("shop_token")
#                 print(shop_name)
#                 print(shop_token)
            

#             pool = await get_db_connection()
#             async with pool.acquire() as connection:
#                 async with connection.cursor() as cursor:
#                     # shop_id = await run_in_threadpool(get_or_create_shop_id, cursor, shop_name)
#                     shop_id = await get_or_create_shop_id(cursor, shop_name)
            
#             pool.close()
#             await pool.wait_closed()

#     except Exception as e:
#         print(f"Error fetching or creating shop_id: {e}")
#         raise HTTPException(status_code=500, detail="Failed to fetch or create shop_id")

#     products = await fetch_shopify_products(shop_token)
#     collection = get_chromadb_collection(shop_name)

#     for index, product in enumerate(products):
#         product_id = product['id']
#         image_src = product['image_src']
#         title = product['title']

#         try:
#             # Download and open the image asynchronously
#             img_response = await run_in_threadpool(requests.get, image_src)
#             if img_response.status_code != 200:
#                 raise ValueError(f"Failed to download image, status code: {img_response.status_code}")

#             try:
#                 img = Image.open(BytesIO(img_response.content))
#             except Exception as e:
#                 raise ValueError(f"Error opening image: {e}")

#             # Resize the image
#             img = img.resize((299, 299))

#             start_time = time.time()

#             # Get embeddings from the in-memory image asynchronously
#             embeddings = await run_in_threadpool(get_embeddings, img)

#             # Upsert the embeddings into ChromaDB asynchronously
#             metadata = title if isinstance(title, dict) else {'title': title}
#             await run_in_threadpool(upsert_to_chromadb, collection, product_id, embeddings, title)

#             end_time = time.time()
#             embedding_time = end_time - start_time
#             print(f"Time from image download to saving in ChromaDB for product {product_id}: {embedding_time:.2f} seconds")

#             print(f"Processed {index + 1}/{len(products)} products. Remaining: {len(products) - (index + 1)}")

#         except Exception as e:
#             print(f"Error processing image for product {product_id} at {image_src}: {e}")

#     try:
#         pool = await get_db_connection()
#         async with pool.acquire() as connection:
#             async with connection.cursor() as cursor:
#                 now = datetime.now().isoformat()  # Get the current time in ISO format
#                 await insert_sync_time(cursor, now, shop_id)
        
#         pool.close()
#         await pool.wait_closed()
        
#     except Exception as e:
#         print(f"Error inserting sync time: {e}")    






# # with shopid function called in this 
# async def process_products(shop_name, shop_token):
#     try:
#         item = await redis.lindex('my_queue', 0)
#         if item:
#             data = json.loads(item)
#             shop_name = data.get("shop_name")
#             shop_token = data.get("shop_token")

#             pool = await get_db_connection()
#             async with pool.acquire() as connection:
#                 async with connection.cursor() as cursor:
#                     shop_id = await run_in_threadpool(get_or_create_shop_id, cursor, shop_name)
            
#             pool.close()
#             await pool.wait_closed()

#     except Exception as e:
#         print(f"Error fetching or creating shop_id: {e}")
#         raise HTTPException(status_code=500, detail="Failed to fetch or create shop_id")

#     products = await fetch_shopify_products(shop_token)
#     collection = get_chromadb_collection(shop_name)

#     for index, product in enumerate(products):
#         product_id = product['id']
#         image_src = product['image_src']
#         title = product['title']

#         try:
#             # Download and open the image asynchronously
#             img_response = await run_in_threadpool(requests.get, image_src)
#             if img_response.status_code != 200:
#                 raise ValueError(f"Failed to download image, status code: {img_response.status_code}")

#             try:
#                 img = Image.open(BytesIO(img_response.content))
#             except Exception as e:
#                 raise ValueError(f"Error opening image: {e}")

#             # Resize the image
#             img = img.resize((299, 299))

#             start_time = time.time()

#             # Get embeddings from the in-memory image asynchronously
#             embeddings = await run_in_threadpool(get_embeddings, img)

#             # Upsert the embeddings into ChromaDB asynchronously
#             metadata = title if isinstance(title, dict) else {'title': title}
#             await run_in_threadpool(upsert_to_chromadb, collection, product_id, embeddings, title)

#             end_time = time.time()
#             embedding_time = end_time - start_time
#             print(f"Time from image download to saving in ChromaDB for product {product_id}: {embedding_time:.2f} seconds")

#             print(f"Processed {index + 1}/{len(products)} products. Remaining: {len(products) - (index + 1)}")

#         except Exception as e:
#             print(f"Error processing image for product {product_id} at {image_src}: {e}")

#     try:
#         pool = await get_db_connection()
#         async with pool.acquire() as connection:
#             async with connection.cursor() as cursor:
#                 now = datetime.now().isoformat()  # Get the current time in ISO format
#                 await insert_sync_time(cursor, now, shop_id)
        
#         pool.close()
#         await pool.wait_closed()
        
#     except Exception as e:
#         print(f"Error inserting sync time: {e}")    


















        
# async def process_products(shop_name, shop_id, shop_token):
#     products = await fetch_shopify_products(shop_token)
#     collection = get_chromadb_collection(shop_name)

#     for index, product in enumerate(products):
#         product_id = product['id']
#         image_src = product['image_src']
#         title = product['title']

#         try:
#             # Download and open the image asynchronously
#             img_response = await run_in_threadpool(requests.get, image_src)
#             if img_response.status_code != 200:
#                 raise ValueError(f"Failed to download image, status code: {img_response.status_code}")

#             try:
#                 img = Image.open(BytesIO(img_response.content))
#             except Exception as e:
#                 raise ValueError(f"Error opening image: {e}")

#             # Resize the image
#             img = img.resize((299, 299))

#             start_time = time.time()

#             # Get embeddings from the in-memory image asynchronously
#             embeddings = await run_in_threadpool(get_embeddings, img)

#             # Upsert the embeddings into ChromaDB asynchronously
#             metadata = title if isinstance(title, dict) else {'title': title}
#             # collection.upsert(ids=[str(product_id)], embeddings=[embeddings], documents=[title])    # doesnt work
#             # await run_in_threadpool(collection.upsert, [str(product_id)], [embeddings],[metadata], [title])  # works
#             # await run_in_threadpool(collection.upsert, [str(product_id)], [embeddings], [metadata] ) # works
#             await run_in_threadpool(upsert_to_chromadb, collection, product_id, embeddings, title)


#             end_time = time.time()
#             embedding_time = end_time - start_time
#             print(f"Time from image download to saving in ChromaDB for product {product_id}: {embedding_time:.2f} seconds")

#             print(f"Processed {index + 1}/{len(products)} products. Remaining: {len(products) - (index + 1)}")

#         except Exception as e:
#             print(f"Error processing image for product {product_id} at {image_src}: {e}")

#     try:
#         pool = await get_db_connection()
#         async with pool.acquire() as connection:
#             async with connection.cursor() as cursor:
#                 now = datetime.now().isoformat()  # Get the current time in ISO format
#                 await insert_sync_time(cursor, now, shop_id)
                
#         pool.close()
#         await pool.wait_closed()
        
#     except Exception as e:
#         print(f"Error inserting sync time: {e}")


# @router.post("/sync")
# async def sync_data(request: Request, background_tasks: BackgroundTasks):
#     try:
#         data = await request.json()
#         shop_name = data.get("shop_name")
#         shop_token = data.get("shop_token")

#         if not shop_name or not shop_token:
#             raise HTTPException(status_code=400, detail="Missing required fields")

#         pool = await get_db_connection()
#         try:
#             async with pool.acquire() as connection:
#                 async with connection.cursor() as cursor:
#                     shop_id = await get_or_create_shop_id(cursor, shop_name)
                
#         finally:
#             pool.close()
#             await pool.wait_closed()

#             # products = await fetch_shopify_products(shop_token)
            
#             # Add the processing task to background tasks
#             background_tasks.add_task(process_products, shop_name,shop_id,shop_token)

#         return {"status": "success"}

#     except HTTPException as e:
#         raise e
    
#     except Exception as e:
#         print(f"Unexpected error: {e}")
#         raise HTTPException(status_code=500, detail="An unexpected error occurred")
    
