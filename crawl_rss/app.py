import httpx
import sqlalchemy
from starlette.config import Config


config = Config(".env")

DEBUG = config("DEBUG", cast=bool, default=False)
DATABASE_URL = config("DATABASE_URL", default="sqlite:///db.sqlite")


http_client = httpx.Client(headers={"User-Agent": "jamey@minilop.net"})

metadata = sqlalchemy.MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)

engine = sqlalchemy.create_engine(DATABASE_URL, echo=DEBUG)

if engine.name == "sqlite":

    @sqlalchemy.event.listens_for(engine, "engine_connect")
    def enable_sqlite_foreign_keys(connection, branch):  # type: ignore
        connection.execute("PRAGMA foreign_keys = ON")
