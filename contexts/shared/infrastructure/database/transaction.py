from contextlib import asynccontextmanager

import tortoise.transactions

from contexts.shared.application.transaction import TransactionManager


class TortoiseTransactionManager(TransactionManager):
    @asynccontextmanager
    async def transaction(self):
        async with tortoise.transactions.in_transaction():
            yield
