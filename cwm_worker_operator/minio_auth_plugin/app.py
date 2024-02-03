from fastapi import FastAPI, Request

app = FastAPI()


@app.post("/")
async def root(request: Request):
    body = await request.json()
    print(body)
    return {"result": True}
