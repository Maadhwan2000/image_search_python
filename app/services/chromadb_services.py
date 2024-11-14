import chromadb
from fastapi import HTTPException
import os


chroma_db_url = os.getenv("CHROMADB_HOST")

#connecting to the chromadb
def get_chromadb_client():
    try:
        # client = chromadb.HttpClient(host='localhost', port=8000)
        client = chromadb.HttpClient(host=chroma_db_url, port=8000)
        print("ChromaDB client connected.")
        return client
    except Exception as e:
        print(f"ChromaDB connection error: {e}")
        return None

client = get_chromadb_client()   #calling the function and this is called in the main file and used in the search and sync file 


# this function gets or creates the collection if it doesnt exist ,  using the store name  , this is called in the sync route file
def get_chromadb_collection(shop_name):
    try:
        collection = client.get_or_create_collection(name=shop_name)
        print(collection)
        return collection
    except Exception as e:
        print(f"ChromaDB connection or collection creation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to connect to ChromaDB or create collection")
    
# same as above function
# this function gets or creates the collection if it doesnt exist ,  using the store name , this is called in the search route file 
def get_chromadb_collection_for_searching(shop_name):
    try:
        collection = client.get_or_create_collection(name=shop_name)
        print(collection)
        return collection
    except Exception as e:
        print(f"ChromaDB connection or collection creation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to connect to ChromaDB or create collection")
    


# deletes the collection for the store
# used in the deletetime api
def del_chromadb_collection(shop_name):
    try:
        collection = client.get_or_create_collection(name=shop_name)
        client.delete_collection(name=shop_name)    
    except Exception as e:
        print(f"ChromaDB connection or collection creation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to connect to ChromaDB or delete collection")





# this function gets or creates the collection if it doesnt exist ,  using the store name 
# not being usedanymore, and was used for some testing 
def get_chromadb_client_and_collection(shop_name):
    try:
        collection = client.get_or_create_collection(name=shop_name)
        print(collection)
        return collection
    except Exception as e:
        print(f"ChromaDB connection or collection creation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to connect to ChromaDB or create collection")