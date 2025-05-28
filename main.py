from fastapi import FastAPI
from starlette.middleware.wsgi import WSGIMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from Cdash_app import create_Cdash_app
from dash_app import create_dash_app


# DB 관리 모듈 
from dbmanage import init_db
from dbmanage_CNT import init_CNTdb

# DB 초기화 = app 생성 전
# init_db() 
# init_CNTdb()
#5.28 DB 백업 이후 초기화 로직 제거 (무결성 검사 O)

app = FastAPI()

# Mount Dash apps
app.mount("/dash/", WSGIMiddleware(create_dash_app().server))
app.mount("/dash2/", WSGIMiddleware(create_Cdash_app().server))

app.mount("/html", StaticFiles(directory="html"), name="html")

@app.get("/")
async def read_index():
    return FileResponse("html/index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", port=8000, reload=True)
