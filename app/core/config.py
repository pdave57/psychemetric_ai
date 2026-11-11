import os

#load environment variables from .env file
DATABASE_URL=os.getenv("DATABASE_URL","sqlite:///./psychemetre.db")
APP_ENV=os.getenv("APP_ENV","development")
