from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from parser.db.models import User


async def create_user(session: AsyncSession, username: str, password: str,
                      real_name: str = None, email: str = None, phone: str = None) -> int:
    user = User(username=username, password=password, real_name=real_name, email=email, phone=phone)
    session.add(user)
    await session.flush()
    return user.id


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    result = await session.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)
