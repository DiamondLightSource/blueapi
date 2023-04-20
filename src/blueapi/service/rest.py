from blueapi.service.routes import router
from fastapi import FastAPI

app = FastAPI()

# here, do app.include_router from all the other routes you want.
app.include_router(router)
