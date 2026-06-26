from db.connection import execute
from db.tables import users


async def create_user(username: str, password: str, real_name: str = None,
                      email: str = None, phone: str = None) -> int:
    result = await execute(users.insert().values(
        username=username, password=password,
        real_name=real_name, email=email, phone=phone,
    ))
    return result.lastrowid


async def get_user_by_username(username: str) -> dict | None:
    result = await execute(users.select().where(users.c.username == username))
    row = await result.fetchone()
    return dict(row) if row else None


async def get_user_by_id(user_id: int) -> dict | None:
    result = await execute(users.select().where(users.c.id == user_id))
    row = await result.fetchone()
    return dict(row) if row else None
