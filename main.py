from fastapi import FastAPI
from starlette.middleware.wsgi import WSGIMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dash_app import create_dash_app

app = FastAPI()

app.mount("/dash/", WSGIMiddleware(create_dash_app().server))
app.mount("/html", StaticFiles(directory="html"), name="html")

@app.get("/")
async def read_index():
    return FileResponse("html/index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", port=8000, reload=True)

