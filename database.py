from tortoise import Tortoise, fields
from tortoise.models import Model


class User(Model):
    id = fields.BigIntField(pk=True)
    map_center_latitude = fields.FloatField(null=True)
    map_center_longitude = fields.FloatField(null=True)
    is_admin = fields.BooleanField(default=False)


class Marker(Model):
    id = fields.IntField(pk=True)
    user_id = fields.BigIntField()
    latitude = fields.FloatField()
    longitude = fields.FloatField()
    comment = fields.TextField()
    created_at = fields.DatetimeField(auto_now_add=True)
    delete_requests = fields.ManyToManyField("models.User", related_name="delete_requests")


async def init_db():
    await Tortoise.init(db_url="sqlite://db.sqlite3", modules={"models": ["database"]})
    await Tortoise.generate_schemas()
