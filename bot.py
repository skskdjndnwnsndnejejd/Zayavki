import json
import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

from config import TOKEN, ADMINS

bot = Bot(token=TOKEN, parse_mode="HTML")
dp = Dispatcher(bot, storage=MemoryStorage())
logging.basicConfig(level=logging.INFO)

# ---------- ПУТИ ДЛЯ ФАЙЛОВ ----------
GROUPS_FILE = "data/groups.json"
INVITES_FILE = "data/invites.json"

PHOTO_ID = "AgACAgQAAxkBA..."


# ---------- ЗАГРУЗКА/СОХРАНЕНИЕ JSON ----------
def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return [] if "groups" in path else {}


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# ---------- FSM ----------
class Form(StatesGroup):
    profit = State()
    experience = State()
    experience_type = State()
    custom = State()


# ---------- Команда /start ----------
@dp.message_handler(commands=["start"])
async def start_cmd(message: types.Message):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Начать", callback_data="start_form"))

    await message.answer_photo(
        PHOTO_ID,
        caption="<b>Здравствуйте!</b>\n<i>Подайте анкету и получите ссылку в нашу тиму «Molynew Team».</i>\nПо вопросам: @MolynewSupportBot",
        reply_markup=kb
    )


# ---------- Запуск анкеты ----------
@dp.callback_query_handler(lambda c: c.data == "start_form")
async def start_form(callback: types.CallbackQuery):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Да", callback_data="profit_yes"))
    kb.add(types.InlineKeyboardButton("Нет", callback_data="profit_no"))

    await callback.message.edit_caption(
        "<b>Анкета</b>\n<i>Согласны ли вы делить профит 60/40 с командой?</i>",
        reply_markup=kb
    )
    await Form.profit.set()


# ---------- Ответ на вопрос №1 ----------
@dp.callback_query_handler(lambda c: c.data in ["profit_yes", "profit_no"], state=Form.profit)
async def profit_answer(callback: types.CallbackQuery, state: FSMContext):

    if callback.data == "profit_no":
        await callback.message.edit_caption("<b>❌ Ваша заявка отклонена.</b>")
        await state.finish()
        return

    await state.update_data(profit=True)

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Да", callback_data="exp_yes"))
    kb.add(types.InlineKeyboardButton("Нет", callback_data="exp_no"))

    await callback.message.edit_caption(
        "<b>Анкета</b>\n<i>Был ли у вас опыт в ск@м сфере раньше?</i>",
        reply_markup=kb
    )
    await Form.experience.set()


# ---------- Ответ на вопрос №2 ----------
@dp.callback_query_handler(lambda c: c.data in ["exp_yes", "exp_no"], state=Form.experience)
async def experience_answer(callback: types.CallbackQuery, state: FSMContext):

    await state.update_data(experience=callback.data == "exp_yes")

    if callback.data == "exp_no":
        return await approve_user(callback, state)

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Дрейнер", callback_data="type_drainer"))
    kb.add(types.InlineKeyboardButton("ОТС", callback_data="type_ots"))
    kb.add(types.InlineKeyboardButton("Стиллер", callback_data="type_stiller"))
    kb.add(types.InlineKeyboardButton("Гарант", callback_data="type_guarantor"))
    kb.add(types.InlineKeyboardButton("Другое", callback_data="type_other"))

    await callback.message.edit_caption(
        "<b>Анкета</b>\n<i>В какой сфере ворка у вас был опыт?</i>",
        reply_markup=kb
    )
    await Form.experience_type.set()


# ---------- Выбор типа опыта ----------
@dp.callback_query_handler(lambda c: c.data.startswith("type_"), state=Form.experience_type)
async def type_answer(callback: types.CallbackQuery, state: FSMContext):
    t = callback.data.replace("type_", "")

    if t == "other":
        await callback.message.edit_caption(
            "<b>Анкета</b>\n<i>Напишите свой вариант ворка.</i>"
        )
        await Form.custom.set()
        return

    await state.update_data(type=t)
    return await approve_user(callback, state)


# ---------- Пользователь вводит свой вариант ----------
@dp.message_handler(state=Form.custom)
async def custom_type(message: types.Message, state: FSMContext):
    await state.update_data(type=message.text)
    return await approve_user(message, state, is_message=True)


# ---------- ОДОБРЕНИЕ + выдача ссылки ----------
async def approve_user(obj, state: FSMContext, is_message=False):
    user_id = obj.from_user.id
    groups = load_json(GROUPS_FILE)
    invites = load_json(INVITES_FILE)

    if not groups:
        text = "<b>Ошибка:</b> нет добавленных групп."
        return await (obj.answer(text) if is_message else obj.message.edit_caption(text))

    target = groups[0]

    # Удаляем старую ссылку
    try:
        old = invites.get(str(user_id))
        if old:
            await bot.revoke_chat_invite_link(target, old)
    except:
        pass

    # Создаём новую
    invite = await bot.create_chat_invite_link(target, name=f"user_{user_id}")

    invites[str(user_id)] = invite.invite_link
    save_json(INVITES_FILE, invites)

    text = (
        "<b>Ваша анкета одобрена!</b>\n"
        "Ваша ссылка: "
        f"{invite.invite_link}"
    )

    # Главное меню
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Gift Castle", url="https://t.me/Giftcastlebot"))
    kb.add(types.InlineKeyboardButton("Castle Выплаты", url="https://t.me/GiftCastlepayments"))
    kb.add(types.InlineKeyboardButton("Castle Мануалы", url="https://t.me/GiftCastleManuals"))

    await (obj.answer(text, reply_markup=kb) if is_message else obj.message.edit_caption(text, reply_markup=kb))
    await state.finish()


# ---------- Добавление группы (только админ) ----------
@dp.message_handler(commands=["addgroup"])
async def add_group(message: types.Message):
    if message.from_user.id not in ADMINS:
        return await message.reply("⛔ Нет доступа.")

    if not message.reply_to_message or not message.reply_to_message.forward_from_chat:
        return await message.reply("Перешлите сообщение из группы и напишите: /addgroup")

    chat = message.reply_to_message.forward_from_chat

    groups = load_json(GROUPS_FILE)
    groups.append(chat.id)
    save_json(GROUPS_FILE, groups)

    await message.reply(f"Группа <b>{chat.title}</b> добавлена!")


# ---------- START ----------
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
