import os
DATABASE_URL=os.getenv("DATABASE_URL","sqlite:///./innermap.db")
APP_ENV=os.getenv("APP_ENV","development")
