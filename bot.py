import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from rabbit import Rabbit
from datetime import datetime
from aiogram.types import FSInputFile

BOT_TOKEN = "TOKEN"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

class State:
    ADD_NAME = 1
    ADD_GENDER = 2
    ADD_FATHER = 3

user_states = {}

@dp.message(Command("start"))
async def start_command_handler(message: types.Message):
    chat_name = message.chat.title if hasattr(message.chat, 'title') else (
        message.chat.username if hasattr(message.chat, 'username') else "Личный чат"
    )
    
    Rabbit.register_chat(message.chat.id, chat_name)
    
    kb = [
        [InlineKeyboardButton(text="📋 Список кроликов", callback_data="list_rabbits")],
        [InlineKeyboardButton(text="➕ Добавить кролика", callback_data="add_rabbit")]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=kb)
    
    await message.answer_photo(
        caption="🐰 Бот для учета кроликов\nВыберите действие:",
        photo=FSInputFile("scheme.png"),
        reply_markup=keyboard
    )

@dp.callback_query(lambda c: c.data == "list_rabbits")
async def list_rabbits(callback: types.CallbackQuery):
    empty_rabbit = Rabbit(0)
    rabbits = empty_rabbit.rabbits_data.find({})

    if not rabbits:
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(
            text="➕ Добавить кролика",
            callback_data="add_rabbit"
        ))
        builder.add(InlineKeyboardButton(
            text="🔙 В меню",
            callback_data="menu"
        ))
        builder.adjust(1)
        
        await callback.message.edit_text(
            "📋 Список кроликов пуст!",
            reply_markup=builder.as_markup()
        )
    else:
        builder = InlineKeyboardBuilder()
        
        for rabbit in sorted(rabbits, key=lambda x: x.get("id", 0)):
            if rabbit.get("is_empty", True): continue
            gender_emoji = "♂️" if rabbit.get("gender") == "male" else "♀️"
            name = rabbit.get("name", "Без имени")
            cell_id = rabbit.get("id", "?")
            
            builder.add(InlineKeyboardButton(
                text=f"{name} {gender_emoji} (клетка {cell_id})",
                callback_data=f"rabbit_{cell_id}"
            ))
        
        builder.add(InlineKeyboardButton(
            text="🔙 В меню",
            callback_data="menu"
        ))
        
        builder.adjust(1)
        
        await callback.message.edit_caption(
            caption="📋 Список кроликов:",
            reply_markup=builder.as_markup()
        )
    
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("rabbit_"))
async def show_rabbit(callback: types.CallbackQuery):
    rabbit_id = int(callback.data.split("_")[1])
    rabbit = Rabbit(rabbit_id)
    
    builder = InlineKeyboardBuilder()
    
    if not rabbit.is_empty:
        builder.add(InlineKeyboardButton(
            text="💞 Случить",
            callback_data=f"breed_{rabbit_id}"
        ))
        
        if rabbit.gender == "female" and rabbit.last_breeding_date:
            builder.add(InlineKeyboardButton(
                text="🔄 Сбросить случку",
                callback_data=f"reset_breed_{rabbit_id}"
            ))
        
        builder.add(InlineKeyboardButton(
            text="✏️ Редактировать",
            callback_data=f"edit_{rabbit_id}"
        ))
        builder.add(InlineKeyboardButton(
            text="🗑️ Удалить",
            callback_data=f"delete_{rabbit_id}"
        ))
    
    builder.add(InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="list_rabbits"
    ))
    builder.adjust(1)
    
    await callback.message.edit_caption(
        caption=rabbit.get_message(),
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data == "add_rabbit")
async def add_rabbit_start(callback: types.CallbackQuery):
    user_states[callback.from_user.id] = {"state": State.ADD_NAME}
    
    await callback.message.edit_caption(
        caption="Введите номер клетки для нового кролика:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="cancel")]
        ])
    )
    await callback.answer()

@dp.message(lambda message: user_states.get(message.from_user.id, {}).get("state") == State.ADD_NAME)
async def add_rabbit_name(message: types.Message):
    user_state = user_states[message.from_user.id]
    try:
        cell_id = int(message.text)
        user_state["cell_id"] = cell_id
        user_state["state"] = State.ADD_GENDER
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="♂️ Самец", callback_data="gender_male"),
                InlineKeyboardButton(text="♀️ Самка", callback_data="gender_female")
            ],
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="cancel")]
        ])
        
        await message.answer(
            "Выберите пол кролика:",
            reply_markup=kb
        )
    except ValueError:
        await message.answer("Пожалуйста, введите корректный номер клетки (число)")

@dp.callback_query(lambda c: c.data.startswith("gender_"))
async def add_rabbit_gender(callback: types.CallbackQuery):
    user_state = user_states.get(callback.from_user.id)
    if not user_state:
        await callback.answer("Сессия истекла, начните заново")
        return
    
    gender = callback.data.split("_")[1]
    user_state["gender"] = gender
    user_state["state"] = State.ADD_FATHER
    
    await callback.message.edit_text(
        "Введите имя кролика:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="cancel")]
        ])
    )
    await callback.answer()

@dp.message(lambda message: user_states.get(message.from_user.id, {}).get("state") == State.ADD_FATHER)
async def add_rabbit_father(message: types.Message):
    user_state = user_states[message.from_user.id]
    name = message.text
    
    rabbit = Rabbit(user_state["cell_id"])
    rabbit.update_rabbit(
        name=name,
        id=user_state["cell_id"],
        gender=user_state["gender"],
        is_empty=False,
        date=datetime.now(),
        last_breeding_date=None,
        father=None
    )
    
    del user_states[message.from_user.id]
    
    await message.answer_photo(
        caption=f"✅ Кролик {name} успешно добавлен в клетку {user_state['cell_id']}!",
        photo=FSInputFile("scheme.png"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 В меню", callback_data="menu")]
        ])
    )

@dp.callback_query(lambda c: c.data.startswith("delete_"))
async def delete_rabbit(callback: types.CallbackQuery):
    rabbit_id = int(callback.data.split("_")[1])
    
    try:
        rabbit = Rabbit(rabbit_id)
        
        if rabbit.is_empty:
            await callback.answer("Клетка уже пуста!")
            return
            
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(
            text="✅ Да, очистить клетку",
            callback_data=f"confirm_delete_{rabbit_id}"
        ))
        builder.add(InlineKeyboardButton(
            text="❌ Нет, оставить",
            callback_data=f"rabbit_{rabbit_id}"
        ))
        
        await callback.message.edit_caption(
            caption=f"Вы уверены, что хотите очистить клетку {rabbit_id}?\nКролик {rabbit.name} будет удален.",
            reply_markup=builder.as_markup()
        )
        
    except Exception as e:
        logging.error(f"Ошибка при удалении кролика: {e}")
        await callback.message.edit_caption(
            caption="⚠️ Произошла ошибка при попытке удаления",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data=f"rabbit_{rabbit_id}")]
            ])
        )
    
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("confirm_delete_"))
async def confirm_delete_rabbit(callback: types.CallbackQuery):
    rabbit_id = int(callback.data.split("_")[2])
    
    try:
        rabbit = Rabbit(rabbit_id)
        rabbit.is_empty = True
        rabbit.save_rabbit()

        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(
            text="🔙 К списку кроликов",
            callback_data="list_rabbits"
        ))
        builder.add(InlineKeyboardButton(
            text="🏠 В меню",
            callback_data="menu"
        ))
        
        await callback.message.edit_caption(
            caption=f"✅ Клетка {rabbit_id} успешно очищена!",
            reply_markup=builder.as_markup()
        )
        
    except Exception as e:
        logging.error(f"Ошибка при подтверждении удаления: {e}")
        await callback.message.edit_caption(
            caption="⚠️ Произошла ошибка при очистке клетки",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data=f"rabbit_{rabbit_id}")]
            ])
        )
    
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("breed_"))
async def breed_rabbit_select(callback: types.CallbackQuery):
    rabbit_id = int(callback.data.split("_")[1])
    current_rabbit = Rabbit(rabbit_id)
    
    all_rabbits = list(current_rabbit.rabbits_data.find({"is_empty": False}))
    
    builder = InlineKeyboardBuilder()
    
    for rabbit_data in all_rabbits:
        if rabbit_data["id"] == rabbit_id:
            continue
            
        partner = Rabbit(rabbit_data["id"])
        
        if current_rabbit.gender != partner.gender:  # Разные полы
            if partner.gender == "female":
                if partner.check_rabbit():
                    gender_emoji = "♀️" if partner.gender == "female" else "♂️"
                    builder.add(InlineKeyboardButton(
                        text=f"{partner.name} {gender_emoji} (клетка {partner.id})",
                        callback_data=f"brabbit_breed_{rabbit_id}_{partner.id}"
                    ))
            else:
                gender_emoji = "♀️" if partner.gender == "female" else "♂️"
                builder.add(InlineKeyboardButton(
                    text=f"{partner.name} {gender_emoji} (клетка {partner.id})",
                    callback_data=f"brabbit_breed_{rabbit_id}_{partner.id}"
                ))
    
    if builder.buttons:
        builder.add(InlineKeyboardButton(
            text="🔙 Назад",
            callback_data=f"rabbit_{rabbit_id}"
        ))
        builder.adjust(1)
        
        await callback.message.edit_caption(
            caption=f"Выберите партнера для {current_rabbit.name} ({'самки' if current_rabbit.gender == 'female' else 'самца'}):",
            reply_markup=builder.as_markup()
        )
    else:
        await callback.message.edit_caption(
            caption="❌ Нет подходящих кроликов для случки!\nУбедитесь, что:\n- Есть кролики противоположного пола\n- Самки готовы к случке (прошло 30 дней)",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data=f"rabbit_{rabbit_id}")]
            ])
        )
    
    user_states[callback.from_user.id] = {
        "state": "BREED_SELECT",
        "rabbit_id": rabbit_id
    }
    
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("brabbit_breed_"))
async def breed_rabbit_confirm(callback: types.CallbackQuery):
    try:
        _, _, rabbit1_id, rabbit2_id = callback.data.split('_')
        rabbit1_id = int(rabbit1_id)
        rabbit2_id = int(rabbit2_id)
        
        rabbit1 = Rabbit(rabbit1_id)
        rabbit2 = Rabbit(rabbit2_id)
        
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(
            text="✅ Подтвердить случку",
            callback_data=f"confirm_breed_{rabbit1_id}_{rabbit2_id}"
        ))
        builder.add(InlineKeyboardButton(
            text="❌ Отменить",
            callback_data=f"rabbit_{rabbit1_id}"
        ))
        
        message = (
            f"Вы уверены, что хотите случить кроликов?\n\n"
            f"🐰 {rabbit1.name} ({'самка' if rabbit1.gender == 'female' else 'самец'}, клетка {rabbit1.id})\n"
            f"🐰 {rabbit2.name} ({'самка' if rabbit2.gender == 'female' else 'самец'}, клетка {rabbit2.id})\n\n"
        )
        
        if rabbit1.gender == "female":
            if rabbit1.check_rabbit():
                message += "Самка готова к случке ✅"
            else:
                days_passed = (datetime.now() - rabbit1.last_breeding_date).days
                message += f"Самка не готова! Прошло только {days_passed} из 30 дней ❌"
        elif rabbit2.gender == "female":
            if rabbit2.check_rabbit():
                message += "Самка готова к случке ✅"
            else:
                days_passed = (datetime.now() - rabbit2.last_breeding_date).days
                message += f"Самка не готова! Прошло только {days_passed} из 30 дней ❌"
        
        await callback.message.edit_caption(
            caption=message,
            reply_markup=builder.as_markup()
        )
        
    except Exception as e:
        logging.error(f"Ошибка при подтверждении случки: {e}")
        await callback.message.edit_caption(
            caption="⚠️ Произошла ошибка при обработке запроса",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="list_rabbits")]
            ])
        )
    
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("confirm_breed_"))
async def process_breeding(callback: types.CallbackQuery):
    try:
        _, _, rabbit1_id, rabbit2_id = callback.data.split('_')
        rabbit1_id = int(rabbit1_id)
        rabbit2_id = int(rabbit2_id)
        
        rabbit1 = Rabbit(rabbit1_id)
        rabbit2 = Rabbit(rabbit2_id)
        
        success = False
        if rabbit1.gender != rabbit2.gender:
            female = rabbit1 if rabbit1.gender == "female" else rabbit2
            if female.check_rabbit():
                female.last_breeding_date = datetime.now()
                female.save_rabbit()
                success = True
        
        # Формируем результат
        if success:
            message = (
                "✅ Случка успешно проведена!\n"
                f"Самка {female.name} теперь не готова к новой случке в течение 30 дней."
            )
        else:
            message = (
                "❌ Не удалось провести случку!\n"
                "Возможные причины:\n"
                "- Кролики одного пола\n"
                "- Самка не готова к случке\n"
                "- Произошла ошибка при сохранении"
            )
        
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(
            text="🔙 К списку кроликов",
            callback_data="list_rabbits"
        ))
        if success:
            builder.add(InlineKeyboardButton(
                text="🐰 Посмотреть самку",
                callback_data=f"rabbit_{female.id}"
            ))
        
        await callback.message.edit_caption(
            caption=message,
            reply_markup=builder.as_markup()
        )
        
    except Exception as e:
        logging.error(f"Ошибка при обработке случки: {e}")
        await callback.message.edit_caption(
            caption="⚠️ Произошла ошибка при обработке случки",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="list_rabbits")]
            ])
        )
    
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("reset_breed_"))
async def reset_breeding_start(callback: types.CallbackQuery):
    rabbit_id = int(callback.data.split("_")[2])
    rabbit = Rabbit(rabbit_id)
    
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="✅ Да, сбросить",
        callback_data=f"confirm_reset_{rabbit_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="❌ Нет, оставить",
        callback_data=f"rabbit_{rabbit_id}"
    ))
    
    last_breeding = rabbit.last_breeding_date.strftime("%Y-%m-%d") if rabbit.last_breeding_date else "не было"
    
    await callback.message.edit_caption(
        caption=f"Вы уверены, что хотите сбросить дату случки для {rabbit.name}?\nТекущая дата последней случки: {last_breeding}\nПосле сброса самка будет считаться готовой к случке.",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("confirm_reset_"))
async def confirm_reset_breeding(callback: types.CallbackQuery):
    rabbit_id = int(callback.data.split("_")[2])
    rabbit = Rabbit(rabbit_id)
    
    if rabbit.reset_breeding():
        message = f"✅ Дата случки для {rabbit.name} сброшена!\nТеперь она готова к новой случке."
    else:
        message = "❌ Ошибка! Можно сбрасывать только для самок."
    
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="🔙 К карточке кролика",
        callback_data=f"rabbit_{rabbit_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="📋 К списку кроликов",
        callback_data="list_rabbits"
    ))
    
    await callback.message.edit_caption(
        caption=message,
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "cancel")
async def cancel_action(callback: types.CallbackQuery):
    if callback.from_user.id in user_states:
        del user_states[callback.from_user.id]
    
    await callback.message.edit_caption(
        caption="Действие отменено",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 В меню", callback_data="menu")]
        ])
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu")
async def back_to_menu(callback: types.CallbackQuery):
    if callback.from_user.id in user_states:
        del user_states[callback.from_user.id]
    
    await start_command_handler(callback.message)
    await callback.answer()

async def check_pregnant_rabbits():
    while True:
        try:
            pregnant_females = Rabbit.get_pregnant_females()
            notifications = []
            
            for female in pregnant_females:
                status = female.get_pregnancy_status()
                if status == "okrol":
                    notifications.append(
                        f"⚠️ Самка {female.name} (клетка {female.id}) должна окролиться "
                        f"в ближайшие дни! (последняя случка {female.last_breeding_date.strftime('%Y-%m-%d')})"
                    )
                elif status == "preparing":
                    days_left = 28 - (datetime.now() - female.last_breeding_date).days
                    notifications.append(
                        f"ℹ️ Самка {female.name} (клетка {female.id}) готовится к окролу. "
                        f"До родов осталось ~{days_left} дней."
                    )
            
            if notifications:
                
                for admin_id in Rabbit.get_active_chats():
                    try:
                        await bot.send_message(
                            admin_id["chat_id"],
                            "🐇 Уведомление о беременных самках:\n\n" + "\n\n".join(notifications)
                        )
                    except Exception as e:
                        logging.error(f"Не удалось отправить уведомление admin {admin_id}: {e}")
            
            await asyncio.sleep(12 * 60 * 60)
            
        except Exception as e:
            logging.error(f"Ошибка в check_pregnant_rabbits: {e}")
            await asyncio.sleep(60)

async def main():
    asyncio.create_task(check_pregnant_rabbits())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
