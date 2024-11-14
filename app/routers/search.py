from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from PIL import Image
import io
from app.services.model_service import get_embeddings   
from app.services.chromadb_services import get_chromadb_collection_for_searching 

router = APIRouter()

# /upload endpoint
@router.post("/upload")
async def upload_image(shop_name: str = Form(...), file: UploadFile = File(...)):
    try:
        #if shop name not sent in the api
        if not shop_name:
            raise HTTPException(status_code=400, detail="Missing required field: shop_name")

        contents = await file.read()
        # img = Image.open(io.BytesIO(contents))

        print(f"Received file content length: {len(contents)}")
        try:
            img = Image.open(io.BytesIO(contents))
        except IOError as e:
            print(f"Image processing error: {e}")
            raise HTTPException(status_code=400, detail="Invalid image file")
        
        #png file not supported so convert png to rgb
        if file.content_type == 'image/png':
            img = img.convert('RGB')

        img = img.resize((299, 299)) #resizing to the supported size by the model 
        embeddings = get_embeddings(img) # converting it into vector embedding

        # getting the collection from chromadb
        collection = get_chromadb_collection_for_searching(shop_name)

        ##chromadb query, more info on this in the chromadb docs 
        # return only the first 13 results where status is active 
        results = collection.query(query_embeddings=embeddings, n_results=13,where={"status": "active"}) 


#approach didnt work 
#         categories_list = top_categories.split(',')
#         category1, category2, category3, category4 = categories_list

#         where_document = {
#     "$or": [
#         {"$contains": category1},
#         {"$contains": category2},
#         {"$contains": category3},
#         {"$contains": category4}
#     ]
# }

#         results = collection.query(
#     query_embeddings=[embeddings],
#     where_document=where_document 
# )
#         print(results)
        


        return {"status": "success", "results": results['ids'][0], "documents": results['documents'][0] , "MetaData": results['metadatas'][0]}
    
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")





## work below is for when tested with different models 





# # # this was done for the testing of EfficientNetB7 model ,  approach didnt work
# @router.post("/upload")
# async def upload_image(shop_name: str = Form(...), file: UploadFile = File(...)):
#     try:
#         if not shop_name:
#             raise HTTPException(status_code=400, detail="Missing required field: shop_name")

#         contents = await file.read()
#         print(f"Received file content length: {len(contents)}")

#         try:
#             img = Image.open(io.BytesIO(contents))
#         except IOError as e:
#             print(f"Image processing error: {e}")
#             raise HTTPException(status_code=400, detail="Invalid image file")

#         img = img.resize((600, 600))
#         embeddings, top_categories = get_embeddings_and_predictions(img)
#         collection = get_chromadb_collection(shop_name)

#         categories_list = top_categories.split(',')
#         category1, category2, category3, category4 = categories_list

#         where_document = {
#             "$or": [
#                 {"$contains": category1},
#                 {"$contains": category2},
#                 {"$contains": category3},
#                 {"$contains": category4}
#             ]
#         }


#         # where_document = {"$contains": category1}

#         results = collection.query(
#             query_embeddings=[embeddings],
#             where_document=where_document
#         )

#         if not results or 'ids' not in results or not results['ids']:
#             raise HTTPException(status_code=500, detail="No results returned from query.")

#         print(f"Results: {results}")

#         return {
#             "status": "success",
#             "results": results['ids'][0],
#             "documents": results['documents'][0],
#             "MetaData": results['metadatas'][0]
#         }

#     except Exception as e:
#         print(f"Error: {e}")
#         raise HTTPException(status_code=500, detail="An unexpected error occurred")



