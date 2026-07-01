
from db.models import UploadBatch, UploadLog
from repositories.base import BaseRepo


class BatchRepo(BaseRepo):
    model = UploadBatch


class LogRepo(BaseRepo):
    model = UploadLog
