from fastapi import APIRouter, HTTPException, Request , BackgroundTasks
import aiomysql
from app.db.connections import get_db_connection
from app.services.chromadb_services import get_chromadb_collection
from app.services.model_service import get_embeddings, clear_cache   
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
import json
import redis.asyncio as redis
import os
import redis.asyncio as redis
from dotenv import load_dotenv
from httpx import RequestError, TimeoutException
load_dotenv()
from datetime import timedelta
import gc
from app.routers.count import countobj 

redis_url = os.getenv("REDIS_URL")
redis_db = int(os.getenv("REDIS_DB"))

# redis_url = "redis://127.0.0.1:6379"  
# redis_db = 0 

router = APIRouter()
redis_client = redis.from_url(redis_url, db=redis_db)  

# for testing 
# redis_client = redis.from_url("redis://172.19.0.3:6379", db=0)
# redis_client = redis.from_url("redis://127.0.0.1:6379", db=0)
#redis_client = redis.from_url("redis://host.docker.internal:6379", db=0)
# redis_client = redis.from_url("redis://localhost:6379", db=0)
# redis = redis.Redis(host='localhost', port=6379, db=0)

processing = False



# all the functions being used in the sync api have been written here
# these functioon can later be put in different folders to follow FastApis folder structure


# this function gets all the products using the shopify api
async def fetch_shopify_products(shop_token: str, shop_name: str, sync_time: int , max_retries: int = 3, retry_delay: float = 1.0):
    # old urls 
    # api_url = f'https://{shop_name}/admin/api/2024-01/products.json?fields=id,image,title,handle,variants,tags,vendor,product_type&limit=250&status=active'
    # api_url = f'https://{shop_name}/admin/api/2024-01/products.json?fields=id,image,status,title,handle,variants,tags,vendor,product_type&limit=250'
    # headers = {'X-Shopify-Access-Token': shop_token}
    
    all_products = []  # empty array
    count = 1          # count of page we fetching

    # select url based on sync time 
    # if sync_time 0, it means that we are performing a sync all all products
    if sync_time == 0:
        api_url = f'https://{shop_name}/admin/api/2024-01/products.json?fields=id,image,status,title,handle,variants,tags,vendor,product_type&limit=250'

    #if sync time is not 0 , then we only sync products updated after the sync date 
    else:
        utc_time = sync_time - timedelta(hours=5)  # my server is in pk time so subtracting 5 

        # convert  datetime object to ISO 8601 format
        formatted_datetime = utc_time.strftime('%Y-%m-%dT%H:%M:%S+00:00')

        api_url = f'https://{shop_name}/admin/api/2024-01/products.json?fields=id,image,status,title,handle,variants,tags,vendor,product_type&limit=250&updated_at_min={formatted_datetime}'


    headers = {'X-Shopify-Access-Token': shop_token}

    async with httpx.AsyncClient(timeout=20) as client:
        while api_url:       # since pagination has a link for the nex tpage, we update the api_url everytime and this loops iterates till not empy
            print(f"Fetching page: {count}")
            retries = 0
            
            # this is done since getching multiple pages causes error, so i try thrice for each page if there is an error
            while retries < max_retries:
                try:
                    response = await client.get(api_url, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                    products = data.get('products', [])

                    # for loop to iterate through and extract info form products
                    for product in products:
                        product_id = product.get('id')
                        image = product.get('image')
                        title = product.get('title')
                        handle = product.get('handle')
                        tags = product.get('tags')
                        vendor = product.get('vendor')
                        product_type = product.get('product_type')
                        status=product.get('status')

                        price = product['variants'][0].get('price')
                        compare_at_price = product['variants'][0].get('compare_at_price', None) or -1
                        image_src = image.get('src') if image else None
                        if product_id and image_src:
                            all_products.append({
                                'id': product_id,
                                'image_src': image_src,
                                'title': title,
                                'handle': handle,
                                'price': price,
                                'tags': tags,
                                'vendor': vendor,
                                'product_type': product_type,
                                'compare_at_price': compare_at_price,
                                'status':status
                            })

                    link_header = response.headers.get('Link', '')
                    # print(f"Link header: {link_header}")

                    # Pagination handling
                    # if contains rel_next then we put that url in api_url varaible 
                    next_url = None
                    if 'rel="next"' in link_header:
                        parts = link_header.split(',')
                        for part in parts:
                            if 'rel="next"' in part:
                                next_url = part.split(';')[0].strip('<> ')
                                break
                    api_url = next_url

                    # increment the page count
                    count += 1
                    break  # Break out of loop if successful

                #retry code 
                except (httpx.HTTPStatusError, RequestError, TimeoutException) as http_err:
                    retries += 1
                    print(f"Error occurred: {http_err} - Retrying ({retries}/{max_retries})...")
                    if retries == max_retries:
                        print("Max retries reached. Exiting.")
                        return all_products
                    await asyncio.sleep(retry_delay * retries)  

                except Exception as err:
                    print(f"An unexpected error occurred: {err}")
                    return all_products

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
        await cursor.execute(sql, (shop_name))
        result = await cursor.fetchone()
        return result[0]
    except aiomysql.Error as e:
        raise HTTPException(status_code=500, detail="An unexpected error occurred")



#we get the sync time from the database
async def get_shop_synctime(cursor, shop_id):
    try:
        sql = "SELECT time FROM sync_time WHERE shop_id = %s"
        await cursor.execute(sql, (shop_id))
        result = await cursor.fetchone()
        if result is None: 
            return 0    
        
        return result[0]  
 
    except aiomysql.Error as e:
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


# get the plan details , status and count 
async def get_pricing_plan(cursor, shop_id):
    try:
        sql = "SELECT product_count, status FROM pricing_plans WHERE shop_id = %s"
        await cursor.execute(sql, (shop_id,))
        result = await cursor.fetchone()
        
        if result is None:
            return {"product_count": 0, "status": "Unknown"}
        
        product_count, status = result
        return {"product_count": product_count, "status": status}
    
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
    #chromdb function , availbale on the chromadb docs
    collection.upsert(
        ids=[str(product_id)], 
        embeddings=[embeddings], 
        metadatas=[metadatas],
        documents=[title]
    )

    # there is a memory leak in when syncing products
    # this was en effort to detect and fix it 
    # this slightly helped 
    del embeddings  # Explicitly delete embeddings
    del metadatas  # Explicitly delete metadatas
    gc.collect()  # Trigger garbage collection


#calls all the function and gets products from shopfy to storing them in the chromadb, this is done in the background and not on the main thread
# this function is also called in the main file
async def process_products():
    global processing 
    #to sollve the memory leak issue
    clear_cache()
    processing = True
    # pool = None
    countobj["total_products"]=0
    countobj["synced_products"]=0
    pool = await get_db_connection()
    try:
        # while processing is true 
        while processing:
            #gets the data from the redis list
            item = await redis_client.lindex('sync_queue1', 0)
            print(item)
            length = await redis_client.llen('sync_queue1')
            # print(f"Length of sync_queue1: {length}")
            if not item:
                processing = False
                break

            #gets the shop name 
            data = json.loads(item)
            shop_name = data.get("shop_name")


            try:
                # pool = await get_db_connection()
                async with pool.acquire() as connection:
                    async with connection.cursor() as cursor:
                        shop_id = await get_or_create_shop_id(cursor, shop_name)
                        # print(shop_id)

                # pool.close()
                # await pool.wait_closed()

            except Exception as e:
                print(f"Error fetching or creating shop_id: {e}")
                # await redis_client.lpop('sync_queue1')
                continue

            try:
                # pool = await get_db_connection()
                async with pool.acquire() as connection:
                    async with connection.cursor() as cursor:
                        shop_token = await get_shop_token(cursor, shop_name)

                # pool.close()
                # await pool.wait_closed()

            except Exception as e:
                print(f"Error fetching shop token: {e}")
                await redis_client.lpop('sync_queue1') # do this so if error it doesnt continue the sync and moves to the next store 
                continue


            # sync time work 
            try:
                # pool = await get_db_connection()
                async with pool.acquire() as connection:
                    async with connection.cursor() as cursor:
                        sync_time = await get_shop_synctime(cursor, shop_id)

                # print(sync_time)
                # pool.close()
                # await pool.wait_closed()

            except Exception as e:
                print(f"Error fetching sync_time: {e}")
                await redis_client.lpop('sync_queue1')
                continue
            
            # sync time work 
            try:
                async with pool.acquire() as connection:
                    async with connection.cursor() as cursor:
                        pricing_plan = await get_pricing_plan(cursor, shop_id)
                        plan_product_count = pricing_plan['product_count']
                        status = pricing_plan['status']

            except Exception as e:
                print(f"Error fetching pricing_plan: {e}")
                await redis_client.lpop('sync_queue1')
                continue


            products = await fetch_shopify_products(shop_token , shop_name, sync_time)
            countobj["shop_name"]=shop_name  #updating the global object with the name and total products
            countobj["total_products"]=len(products)
            collection = get_chromadb_collection(shop_name)

            batch_size = 100
            # for index, product in enumerate(products):
            # this loops means if product count is 0 in the db it eans premium plan and we iterate through all the products
            # if there is a count in the db then we iterate till that count 
            for index, product in enumerate(products if plan_product_count == 0 else products[:plan_product_count]):
                if index > 0 and index % batch_size == 0:
                    gc.collect()   #garbage collection
                    await asyncio.sleep(0)
                
                product_id = product['id']
                image_src = product['image_src']
                title = product['title']
                price = product['price']
                compare_at_price=product['compare_at_price']
                handle = product['handle']
                status = product['status']
                tags = product['tags']
                vendor = product['vendor']
                product_type = product['product_type']

                metadata = {
                'price': price,
                'handle': handle,
                'image_src':image_src,
                'tags':tags,
                'vendor':vendor,
                'product_type':product_type,
                "compare_at_price":compare_at_price,
                "status":status
                }
               

                try:
                    img_response = await run_in_threadpool(requests.get, image_src) # this runs in the background so the main thread is free
                    if img_response.status_code != 200:
                        raise ValueError(f"Failed to download image, status code: {img_response.status_code}")

                    try:
                        img = Image.open(BytesIO(img_response.content))
                        # with Image.open(BytesIO(img_response.content)) as img:
                    except Exception as e:
                        raise ValueError(f"Error opening image: {e}")
                    
                    # all image format works but it causes problem on png so that why converting only png image to rgb
                    if img.format == 'PNG':
                        img = img.convert('RGB')

                    img = img.resize((299, 299)) # resizing to the supported size by the model 
                    start_time = time.time()
                    # converting pic to vector embedding
                    embeddings = await run_in_threadpool(get_embeddings, img)   # get_embeddings(img)

                    # saving vector emebdding to chromadb
                    await run_in_threadpool(upsert_to_chromadb, collection, product_id, embeddings,metadata, title) 

                    #calculating the time for the embedding and processing of the image 
                    end_time = time.time()
                    embedding_time = end_time - start_time
                    img.close()  # done for memory
                    print(f"Time from image download to saving in ChromaDB for product {product_id}: {embedding_time:.2f} seconds")

                    print(f"Processed {index + 1}/{len(products)} products. Remaining: {len(products) - (index + 1)}")
                    countobj["synced_products"]=index + 1

                except Exception as e:
                    print(f"Error processing image for product {product_id} at {image_src}: {e}")

                # done for the memory leak issue
                del img
                del embeddings
                del metadata
                gc.collect()

                # done for the memory leak issue
                if (index + 1) % batch_size == 0:
                    gc.collect()
                    clear_cache()

            try:
                # pool = await get_db_connection()
                async with pool.acquire() as connection:
                    async with connection.cursor() as cursor:
                        now = datetime.now().isoformat()  # Get the current time in ISO format
                        await insert_sync_time(cursor, now, shop_id)

                # pool.close()
                # await pool.wait_closed()

            except Exception as e:
                print(f"Error inserting sync time: {e}")

            # Remove the processed item from the queue
            await redis_client.lpop('sync_queue1')

    except Exception as e:
        print(f"Error processing queue: {e}")

    finally:
        # dont for the memory leak isse
        pool.close()
        await pool.wait_closed()
        processing = False
        gc.collect()
        clear_cache()
        # del products 





#the router
#/sync endpoint
@router.post("/sync")
async def sync_data(request: Request, background_tasks: BackgroundTasks):
    global processing  
    try:
        data = await request.json()
        shop_name = data.get("shop_name")
        length = await redis_client.llen('sync_queue1')
        # print(f"Length of sync_queue1: {length}")
        # await redis_client.delete('sync_queue1')  # This will remove the entire key 'sync_queue1'


        # shop_token = data.get("shop_token")

        if not shop_name: # or not shop_token:
            raise HTTPException(status_code=400, detail="Missing required fields")

    
        data = {
        "shop_name": shop_name #,
        # "shop_token": shop_token
        }

        data_json = json.dumps(data)
        await redis_client.rpush('sync_queue1', data_json)

        if processing == False:
            processing = True # so that the process products functions starts syncing 
            background_tasks.add_task(process_products)  # we send the response to the user and the server syncs in the background 

        return {"status": "success"}

    except HTTPException as e:
        raise e
    
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")
    



















