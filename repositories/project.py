from db.models import Project
from repositories.base import BaseRepo


class ProjectRepo(BaseRepo):
    model = Project
