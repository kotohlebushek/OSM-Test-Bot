from flask import Flask, render_template
from tortoise import Tortoise
from database import init_db, User, Marker
import asyncio

app = Flask(__name__)


def async_to_sync(async_func):
    """Преобразует асинхронную функцию в синхронную"""

    def wrapper(*args, **kwargs):
        return asyncio.run(async_func(*args, **kwargs))

    return wrapper


@app.route("/<int:user_id>.html")
@async_to_sync
async def user_map(user_id):
    user = await User.get_or_none(id=user_id)
    if not user:
        return "Пользователь не найден", 404

    markers = await Marker.all().values("id", "latitude", "longitude", "comment", "created_at")

    return render_template("map_template.html",
                           center_lat=user.map_center_latitude or 55.751244,
                           center_lon=user.map_center_longitude or 37.618423,
                           markers=markers)


async def start_server():
    # Инициализация базы перед запуском
    await init_db()
    # Запуск сервера Flask
    app.run(host="0.0.0.0", port=5000)

    await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(start_server())  # Используем async функцию для запуска
