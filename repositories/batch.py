
from db.tables import upload_batches, upload_logs
from repositories.base import BaseRepo


class BatchRepo(BaseRepo):
    table = upload_batches


class LogRepo(BaseRepo):
    table = upload_logs
