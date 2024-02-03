from fastapi import FastAPI, Request, APIRouter

app = FastAPI()
router = APIRouter()


@router.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH", "TRACE"])
async def catch_all(request: Request, full_path: str):
    try:
        body = await request.body()
    except:
        body = None
    print(f'method: {request.method}, path: /{full_path}, body: {body}')
    return {}


app.include_router(router)
