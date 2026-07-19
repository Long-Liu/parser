from tortoise import migrations
from tortoise.migrations import operations as ops

class Migration(migrations.Migration):
    # Historical migrations 0002-0005 declare no dependencies and are ordered
    # by filename as independent graph roots; depending on all of them would
    # make this component replay in reverse DFS order (0005 before 0001) and
    # break state projection. Chaining onto 0005 keeps the 0001..0006 order.
    dependencies = [('models', '0005_budget_adjustment_settlement')]

    initial = False

    operations = [
        ops.DeleteModel(name='DataGrossProfit'),
        ops.DeleteModel(name='TemplateConfig'),
    ]
