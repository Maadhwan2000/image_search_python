import chromadb
from fastapi import HTTPException

# chroma db authentication wali use kerni hai 
client = chromadb.HttpClient(host='localhost', port=8000)
# client_two = chromadb.HttpClient(host='localhost', port=8000)

def get_chromadb_client_and_collection(shop_name):
    try:
        client = chromadb.HttpClient(host='localhost', port=8000)
        print(client.heartbeat())
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