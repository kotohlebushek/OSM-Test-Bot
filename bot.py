import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from tortoise import Tortoise
from database import init_db, User, Marker
from config import TOKEN, SERVER_URL, ADMIN_ID

bot = Bot(TOKEN)
dp = Dispatcher()


class AddMarker(StatesGroup):
    waiting_location = State()
    waiting_comment = State()


class ChangeCity(StatesGroup):
    waiting_location = State()


class DeleteMarker(StatesGroup):
    waiting_marker_id = State()


def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить метку", callback_data="add_marker")],
        [InlineKeyboardButton(text="Показать карту", callback_data="show_map")],
        [InlineKeyboardButton(text="Удалить метку", callback_data="delete_marker")]
    ])


@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    user, created = await User.get_or_create(id=message.from_user.id)

    if created or user.map_center_latitude is None:
        await state.set_state(ChangeCity.waiting_location)
        await message.answer("Отправьте вашу геолокацию для центра карты.")
    else:
        await message.answer("Выберите действие:", reply_markup=main_keyboard())


@dp.message(F.content_type == "location", ChangeCity.waiting_location)
async def set_user_location(message: types.Message, state: FSMContext):
    user = await User.get(id=message.from_user.id)
    user.map_center_latitude = message.location.latitude
    user.map_center_longitude = message.location.longitude
    await user.save()

    await message.answer("Центр карты установлен.", reply_markup=main_keyboard())
    await state.clear()


@dp.callback_query(F.data == "add_marker")
async def add_marker_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddMarker.waiting_location)
    await callback.message.answer("Отправьте геолокацию метки.")


@dp.message(F.content_type == "location", AddMarker.waiting_location)
async def receive_marker_location(message: types.Message, state: FSMContext):
    await state.update_data(latitude=message.location.latitude, longitude=message.location.longitude)
    await state.set_state(AddMarker.waiting_comment)
    await message.answer("Отправьте комментарий к метке.")


@dp.message(AddMarker.waiting_comment)
async def receive_marker_comment(message: types.Message, state: FSMContext):
    data = await state.get_data()
    latitude, longitude = data["latitude"], data["longitude"]

    existing_marker = await Marker.filter(
        latitude__gte=latitude - 0.001, latitude__lte=latitude + 0.001,
        longitude__gte=longitude - 0.001, longitude__lte=longitude + 0.001
    ).first()

    if existing_marker:
        await message.answer("В этом месте уже есть метка!")
    else:
        await Marker.create(user_id=message.from_user.id, latitude=latitude, longitude=longitude, comment=message.text)
        await message.answer("Метка добавлена.", reply_markup=main_keyboard())

    await state.clear()


@dp.callback_query(F.data == "show_map")
async def show_map_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    await callback.message.answer(f"Ваша карта: {SERVER_URL}/{user_id}.html")


@dp.callback_query(F.data == "delete_marker")
async def delete_marker_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(DeleteMarker.waiting_marker_id)
    await callback.message.answer("Введите ID метки, которую хотите удалить.")


@dp.message(DeleteMarker.waiting_marker_id)
async def delete_marker(message: types.Message, state: FSMContext):
    marker_id = int(message.text)
    marker = await Marker.get_or_none(id=marker_id)

    if not marker:
        await message.answer("Метка не найдена.")
    else:
        user = await User.get_or_none(id=message.from_user.id)  # Get user from DB
        if (
                user and user.is_admin) or marker.user_id == message.from_user.id or message.from_user.id == ADMIN_ID:  # Check if user is creator or admin
            await marker.delete()
            await message.answer("Метка удалена.", reply_markup=main_keyboard())
        else:
            await marker.delete_requests.add(user)  # где user — объект пользователя
            await marker.save()
            await message.answer(
                "Запрос на удаление отправлен. Если 3 разных пользователя отправят запрос, метка будет удалена.")

            if await marker.delete_requests.all().count() >= 3:
                await marker.delete()
                await message.answer("Метка была удалена после 3-х запросов.")

    await state.clear()


@dp.message(Command("change_city"))
async def change_city(message: types.Message, state: FSMContext):
    await state.set_state(ChangeCity.waiting_location)
    await message.answer("Отправьте вашу геолокацию для центра карты.")


@dp.message(Command("add_admin"))
async def add_admin(message: types.Message):
    # Check if the user is an admin
    if message.from_user.id == ADMIN_ID:
        # Split the message text to get the admin ID
        try:
            new_admin_id = int(message.text.split()[1])

            # Update the user's 'is_admin' field in the database
            user = await User.get_or_create(id=new_admin_id)
            user.is_admin = True
            await user.save()

            await message.answer(f"Пользователь с ID {new_admin_id} теперь администратор.")
        except (IndexError, ValueError):
            await message.answer("Пожалуйста, укажите правильный ID пользователя для добавления.")
    else:
        await message.answer("У вас нет прав для выполнения этой команды.")


@dp.message(Command("instruction"))
async def instruction(message: types.Message):
    instruction_text = """
    Привет! Добро пожаловать в бота, который помогает отмечать посты ДПС на карте и делиться этой информацией с другими пользователями. Вот простая инструкция, как использовать бота:

    ---

    Основные функции бота:
    1. Добавить метку — вы можете отправить геопозицию поста ДПС, чтобы добавить её на карту.
    2. Посмотреть карту — получить актуальную карту с отмеченными постами ДПС.
    3. Удалить метку — удалить ранее добавленную метку (если она больше не актуальна).

    ---

    Как пользоваться ботом:

    1. Добавить метку:
       - Нажмите кнопку "Добавить метку".
       - Отправьте геопозицию через Telegram (для этого нажмите на скрепку 📎 → "Геопозиция" и выберите нужное место на карте).
       - Бот добавит метку на карту.

    2. Посмотреть карту:
       - Нажмите кнопку "Посмотреть карту".
       - Бот отправит вам карту с отметками всех постов ДПС, которые были добавлены пользователями.

    3. Удалить метку:
       - Нажмите кнопку "Удалить метку".
       - Отправьте id метки, которую хотите удалить (его мы можете найти в описании к метке).
       - Бот удалит метку, если она была добавлена ранее.

    ---

    Важные моменты:
    - Убедитесь, что вы отправляете точную геопозицию, чтобы другие пользователи могли ориентироваться по карте.
    - Если вы случайно добавили неверную метку, удалите её с помощью кнопки "Удалить метку".
    - Карта обновляется автоматически, поэтому вы всегда будете видеть актуальные данные.

    ---

    Если у вас есть вопросы или что-то не работает, напишите в поддержку. Приятного пользования! 🚗🗺️
    """
    await message.answer(instruction_text)


async def main():
    await init_db()
    await dp.start_polling(bot)
    await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
