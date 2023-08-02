from fastapi import FastAPI

app = FastAPI()


@app.get("/")
async def root():
    return "hi"

# REST API that's effectively a layer on top of the DB/ORM.
