from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.core.config import DATABASE_URL

#database connection settings
kwargs={"check_same_thread":False} if DATABASE_URL.startswith("sqlite") else {}

#create the database engine and session factory
engine=create_engine(DATABASE_URL,connect_args=kwargs,pool_pre_ping=True)
SessionLocal=sessionmaker(bind=engine,autoflush=False,autocommit=False)

class Base(DeclarativeBase): pass
def get_db():
    db=SessionLocal()
    try: yield db
    finally: db.close()
