from app import create_app
import uvicorn

app = create_app()

if __name__ == "__main__":
    from app.config import HOST, PORT
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)