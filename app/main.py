from fastapi import FastAPI, BackgroundTasks
from app.routers import sync
from app.routers import search
from app.routers import delete_queue
from app.routers import count
from app.routers import deleteTime
from app.services.model_service import model  
from PIL import Image
from app.services.model_service import get_embeddings    
from app.services.chromadb_services import get_chromadb_client
from app.routers.sync import process_products
import asyncio
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
from app.routers.count import countobj

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# Configure CORS middleware using environment variables
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),  # Allow origins from env
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

@app.on_event("startup")   # below code is executed when the server starts 
async def startup_event():

    global countobj  #count varaible for product sync count , global

    global model    # the model, this loads up the model when the server starts , otherwise the model will load when the first api is called
    print("Model loaded on startup")

    img = Image.new('RGB', (299, 299))    
    get_embeddings(img)
    print("Model warm-up completed")  # running the model so all its data is loaded

    global client                     #chromadb intialized here , so same connection is used in the server
    client = get_chromadb_client()

    asyncio.create_task(process_products())  #starting process_product task so that if any store in is in queue it starts syncing   , this function is in the sync route file

#all the routes
app.include_router(sync.router)        # sync route
app.include_router(search.router)      # search route
app.include_router(delete_queue.router)  # called when an app is uninstalled and redis queue is checked and if store exists then is removed from there
app.include_router(count.router)       # give the count of the product synced when syncing
app.include_router(deleteTime.router)  #called when the pricing plan is changed, it deletes the chroma collection and also deletes the sync time


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(
        app,
        host=os.getenv("SERVER_HOST"),
        port=int(os.getenv("SERVER_PORT")),
        log_level=os.getenv("LOG_LEVEL")
    )





