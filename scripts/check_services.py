"""Check that local PostgreSQL and Redis (docker compose) are reachable"""

import psycopg
import redis
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    redis_host: str = "localhost"
    redis_port: int = 6379


def check_postgres(settings: Settings) -> str:
    """Connect to postgreSQL and return its version"""
    with psycopg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        dbname=settings.postgres_db,
    ) as conn:
        consulta = conn.execute("SELECT version()").fetchone()
        return consulta[0]


def check_redis(settings: Settings) -> str:
    """Write a new key to redis, read is back and return it"""
    with redis.Redis(
        host=settings.redis_host, port=settings.redis_port, decode_responses=True
    ) as conn:
        conn.set("clave", "valor")
        return conn.get("clave")


def main() -> None:
    settings = Settings()
    print("Postgres:", check_postgres(settings))
    print("Redis: ", check_redis(settings))


if __name__ == "__main__":
    main()
