from fastapi import FastAPI, BackgroundTasks
from app.routers import sync
from app.routers import search
from app.services.model_service import model  
from PIL import Image
from app.services.model_service import get_embeddings  # get_embeddings_and_predictions  
from app.services.chromadb_services import get_chromadb_client
from app.routers.sync import process_products
import asyncio
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

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

@app.on_event("startup")
async def startup_event():

    global model 
    print("Model loaded on startup")

    img = Image.new('RGB', (299, 299))    
    get_embeddings(img)
    print("Model warm-up completed")

    global client
    client = get_chromadb_client()

    asyncio.create_task(process_products())


app.include_router(sync.router)
app.include_router(search.router)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(
        app,
        host=os.getenv("SERVER_HOST"),
        port=int(os.getenv("SERVER_PORT")),
        log_level=os.getenv("LOG_LEVEL")
    )





