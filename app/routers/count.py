countobj = {}

from fastapi import APIRouter, Request, HTTPException
app = APIRouter()

router = APIRouter()

@router.post("/count")
async def get_count(req: Request):
    try:
        body = await req.json()
        
        if "shop_name" not in body:
            raise HTTPException(status_code=400, detail="shop_name is required")
        
        shop_name = body["shop_name"]
        
        if shop_name == countobj.get("shop_name"):
            total_products = countobj.get("total_products", 0)
            synced_products = countobj.get("synced_products", 0)
            return {"total_products": total_products, "synced_products": synced_products}
        else:
            return {"total_products": 0, "synced_products": 0}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")