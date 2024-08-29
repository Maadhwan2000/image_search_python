import chromadb
from fastapi import HTTPException
import os


chroma_db_url = os.getenv("CHROMADB_HOST")
# client = chromadb.HttpClient(host='localhost', port=80100)

def get_chromadb_client():
    try:
        # client = chromadb.HttpClient(host='172.19.0.2', port=8000)
        # client = chromadb.HttpClient(host='localhost', port=8000)
        client = chromadb.HttpClient(host=chroma_db_url, port=8000)
        print("ChromaDB client connected.")
        return client
    except Exception as e:
        print(f"ChromaDB connection error: {e}")
        return None

client = get_chromadb_client()

def get_chromadb_client_and_collection(shop_name):
    try:
        #client = chromadb.HttpClient(host=chromadb_host, port=8000)
        # client = chromadb.HttpClient(host='localhost', port=8000)
        # print(client.heartbeat())
        collection = client.get_or_create_collection(name=shop_name)
        print(collection)
        return collection
        
    except Exception as e:
        print(f"ChromaDB connection or collection creation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to connect to ChromaDB or create collection")


def get_chromadb_collection(shop_name):
    try:
        client.delete_collection(name=shop_name)     # if a product is removed then it isnt removed from chorma , thats why deleting the whole collection so only the latest products show up
        collection = client.get_or_create_collection(name=shop_name)
        print(collection)
        return collection
    except Exception as e:
        print(f"ChromaDB connection or collection creation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to connect to ChromaDB or create collection")
    

def get_chromadb_collection_for_searching(shop_name):
    try:
        collection = client.get_or_create_collection(name=shop_name)
        print(collection)
        return collection
    except Exception as e:
        print(f"ChromaDB connection or collection creation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to connect to ChromaDB or create collection")