import sqlalchemy
from starlette.config import Config


config = Config(".env")

DEBUG = config("DEBUG", cast=bool, default=False)
DATABASE_URL = config("DATABASE_URL", default="sqlite:///db.sqlite")


metadata = sqlalchemy.MetaData()
engine = sqlalchemy.create_engine(DATABASE_URL, echo=DEBUG)

if engine.name == "sqlite":

    @sqlalchemy.event.listens_for(engine, "engine_connect")
    def enable_sqlite_foreign_keys(connection, branch):  # type: ignore
        connection.execute("PRAGMA foreign_keys = ON")
