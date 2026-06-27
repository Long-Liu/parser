from db.tables import projects
from repositories.base import BaseRepo


class ProjectRepo(BaseRepo):
    table = projects
