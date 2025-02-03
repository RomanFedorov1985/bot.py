from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
import json
import nest_asyncio
import os

# Применяем nest_asyncio для работы в Google Colab
nest_asyncio.apply()

# Файл для сохранения заявок
DATA_FILE = "orders.json"

# Файл для сохранения броней
BOOKINGS_FILE = "bookings.json"

# Формулы для расчета материалов
MATERIAL_FORMULAS = {
    "Обычные обои": lambda area: round(area / 5),  # 1 рулон на 5 м², округляем до целого числа
    "Обои с совмещением рисунка": lambda area: round(area / 4),  # 1 рулон на 4 м², округляем до целого числа
    "Клей обойный": lambda area: area / 20,  # 1 пачка клея на 20 м²
    "Краска вододисперсная": lambda area: area * 0.3 * 3,  # 0.3 литра на м² × 3 слоя
    "Укрывная плёнка": lambda area: area * 1.2,  # 1.2 рулона на м²
    "Грунтовка": lambda area: area / 10,  # 1 литр на 10 м²
    "Скотч малярный": lambda perimeter: perimeter * 1.1,  # 1.1 рулона на метр периметра
    "Плинтус потолочный": lambda perimeter: perimeter * 1.05,  # 1.05 метра плинтуса на метр периметра
    "Жидкие гвозди": lambda perimeter: perimeter * 0.05  # 0.05 литров жидких гвоздей на метр периметра
}

# Главное меню
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["Прайс-лист 📝", "Рассчитать стоимость 💳"],
        ["Связаться с мастером 📞", "О мастере 👨‍💼"],
        ["Расчёт материалов 🛠️", "Забронировать 📅"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)

# Прайс-лист
async def price_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prices = """
Прайс-лист:
• Поклейка обоев — 400 ₽ за м² (обычные), 450 ₽ за м² (с совмещением рисунка)
• Покраска стен — 400 ₽ за м²
• Покраска потолков — 450 ₽ за м²
• Демонтаж обоев — 160 ₽
• Покраска стен в два слоя — 400 ₽
• Покраска потолка в два слоя — 450 ₽ за м²
• Покраска полов — от 400 ₽
• Огрунтовка стен — 160 ₽ за м²
• Огрунтовка потолков — 160 ₽ за м²
• Покраска водопроводных труб — 500 ₽ за ед.
• Подготовка поверхностей — от 400 ₽ за м²
• Поклейка фотообоев — от 450 ₽ за м²
• Нанесение фресок — от 1 000 ₽ за м²
• Поклейка стеклообоев — от 600 ₽ за м²
"""
    await update.message.reply_text(prices)

# Рассчитать стоимость
async def calculate_cost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Обычные обои 🪜", callback_data="cost_wallpaper_regular")],
        [InlineKeyboardButton("Обои с совмещением рисунка 🪜", callback_data="cost_wallpaper_pattern")],
        [InlineKeyboardButton("Покраска стен 🖌️", callback_data="cost_paint_walls")],
        [InlineKeyboardButton("Покраска потолков 🖌️", callback_data="cost_paint_ceilings")],
        [InlineKeyboardButton("Другая услуга", callback_data="cost_other_service")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите услугу для расчета:", reply_markup=reply_markup)

# Обработка выбора услуги для расчета
async def cost_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    service = query.data

    if service == "cost_wallpaper_regular":
        context.user_data['service'] = "Поклейка обычных обоев"
        context.user_data['price_per_unit'] = 400
    elif service == "cost_wallpaper_pattern":
        context.user_data['service'] = "Поклейка обоев с совмещением рисунка"
        context.user_data['price_per_unit'] = 450
    elif service == "cost_paint_walls":
        context.user_data['service'] = "Покраска стен"
        context.user_data['price_per_unit'] = 400
    elif service == "cost_paint_ceilings":
        context.user_data['service'] = "Покраска потолков"
        context.user_data['price_per_unit'] = 450
    else:
        # Если выбрана "Другая услуга", отправляем контактную информацию с кнопками
        keyboard = [
            [InlineKeyboardButton("Написать в WhatsApp 📱", url="https://wa.me/79235194888")],
            [InlineKeyboardButton("Написать в Telegram 📲", url="https://t.me/remont42kemerovo")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("""
Выбрана другая услуга. Уточните детали у мастера:
• Телефон/WhatsApp: +7 (923) 519-48-88
• Telegram: @remont42kemerovo
""",
            reply_markup=reply_markup
        )
        return

    # Запрашиваем площадь стен
    await query.edit_message_text("Введите площадь стен в квадратных метрах (например, 20).")
    context.user_data['step'] = "area"

# Обработка ввода данных для расчета стоимости
async def handle_cost_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text

    if 'step' not in context.user_data:
        await update.message.reply_text("Пожалуйста, начните с команды /start.")
        return

    try:
        area = float(user_input)
        service = context.user_data['service']
        price_per_unit = context.user_data['price_per_unit']
        cost = area * price_per_unit
        await update.message.reply_text(f"Стоимость {service} составит: {cost} ₽.")
        save_order(update.message.from_user.username, service, cost)
        context.user_data.clear()
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите корректное число.")

# Сохранение заявки
def save_order(username, service, cost):
    try:
        with open(DATA_FILE, "r") as file:
            data = json.load(file)
    except FileNotFoundError:
        data = []

    order = {
        "username": username,
        "service": service,
        "cost": cost
    }
    data.append(order)

    with open(DATA_FILE, "w") as file:
        json.dump(data, file, indent=4)

# Расчёт материалов
async def calculate_materials(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Обычные обои 🪜", callback_data="materials_wallpaper_regular")],
        [InlineKeyboardButton("Обои с совмещением рисунка 🪜", callback_data="materials_wallpaper_pattern")],
        [InlineKeyboardButton("Клей обойный 🪛", callback_data="materials_glue")],
        [InlineKeyboardButton("Краска вододисперсная 🚰", callback_data="materials_paint")],
        [InlineKeyboardButton("Укрывная плёнка 🌿", callback_data="materials_film")],
        [InlineKeyboardButton("Грунтовка 🪲", callback_data="materials_primer")],
        [InlineKeyboardButton("Скотч малярный 🪝", callback_data="materials_tape")],
        [InlineKeyboardButton("Плинтус потолочный 🪗", callback_data="materials_plinth")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите материал для расчёта:", reply_markup=reply_markup)

# Обработка выбора материала
async def materials_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    material = query.data

    if material == "materials_wallpaper_regular":
        await query.edit_message_text("Введите площадь стен в квадратных метрах (например, 20).")
        context.user_data['material'] = "Обычные обои"
        context.user_data['step'] = "area"
    elif material == "materials_wallpaper_pattern":
        await query.edit_message_text("Введите площадь стен в квадратных метрах (например, 20).")
        context.user_data['material'] = "Обои с совмещением рисунка"
        context.user_data['step'] = "area"
    elif material == "materials_glue":
        await query.edit_message_text("Введите площадь стен в квадратных метрах (например, 20).")
        context.user_data['material'] = "Клей обойный"
        context.user_data['step'] = "area"
    elif material == "materials_paint":
        await query.edit_message_text("Введите площадь стен в квадратных метрах (например, 20).")
        context.user_data['material'] = "Краска вододисперсная"
        context.user_data['step'] = "area"
    elif material == "materials_film":
        await query.edit_message_text("Введите площадь пола в квадратных метрах (например, 15).")
        context.user_data['material'] = "Укрывная плёнка"
        context.user_data['step'] = "floor_area"
    elif material == "materials_primer":
        await query.edit_message_text("Введите площадь стен в квадратных метрах (например, 20).")
        context.user_data['material'] = "Грунтовка"
        context.user_data['step'] = "area"
    elif material == "materials_tape":
        await query.edit_message_text("Введите периметр помещения в метрах (например, 10).")
        context.user_data['material'] = "Скотч малярный"
        context.user_data['step'] = "perimeter"
    elif material == "materials_plinth":
        await query.edit_message_text("Введите периметр помещения в метрах (например, 10).")
        context.user_data['material'] = "Плинтус потолочный"
        context.user_data['step'] = "perimeter"

# Обработка ввода данных для расчёта материалов
async def handle_materials_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text

    if 'step' not in context.user_data:
        await update.message.reply_text("Пожалуйста, начните с команды /start.")
        return

    try:
        value = float(user_input)
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите корректное число.")
        return

    material = context.user_data['material']
    step = context.user_data['step']

    if step == "area":
        formula = MATERIAL_FORMULAS[material]
        result = formula(value)
        await update.message.reply_text(f"Для {value} м² потребуется примерно {result} единиц {material}.")
    elif step == "floor_area":
        formula = MATERIAL_FORMULAS["Укрывная плёнка"]
        result = formula(value)
        await update.message.reply_text(f"Для {value} м² пола потребуется примерно {result:.1f} рулонов укрывной плёнки.")
    elif step == "perimeter":
        formula = MATERIAL_FORMULAS[material]
        result = formula(value)
        await update.message.reply_text(f"Для {value} метров периметра потребуется примерно {result:.1f} единиц {material}.")

    context.user_data.clear()

# Забронировать
async def book_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите ваше имя:")
    context.user_data['step'] = "name"

# Обработка ввода данных для бронирования
async def handle_booking_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text

    if 'step' not in context.user_data:
        await update.message.reply_text("Пожалуйста, начните с команды /start.")
        return

    step = context.user_data['step']

    if step == "name":
        context.user_data['name'] = user_input
        await update.message.reply_text("Введите ваш номер телефона:")
        context.user_data['step'] = "phone"
    elif step == "phone":
        context.user_data['phone'] = user_input
        await update.message.reply_text("Введите адрес:")
        context.user_data['step'] = "address"
    elif step == "address":
        context.user_data['address'] = user_input
        await update.message.reply_text("Введите площадь стен в квадратных метрах (например, 20):")
        context.user_data['step'] = "area"
    elif step == "area":
        try:
            area = float(user_input)
            cost = area * 400  # Пример: 400 ₽ за м²
            context.user_data['area'] = area
            context.user_data['cost'] = cost
            await update.message.reply_text("Введите желаемую дату и время (например, 2023-10-15 14:00):")
            context.user_data['step'] = "datetime"
        except ValueError:
            await update.message.reply_text("Пожалуйста, введите корректное число.")
    elif step == "datetime":
        datetime = user_input
        name = context.user_data['name']
        phone = context.user_data['phone']
        address = context.user_data['address']
        area = context.user_data['area']
        cost = context.user_data['cost']
        await update.message.reply_text(f"""
Бронь успешно создана!
Имя: {name}
Телефон: {phone}
Адрес: {address}
Площадь стен: {area} м²
Стоимость: {cost} ₽
Дата и время: {datetime}
""")
        save_booking(name, phone, address, area, cost, datetime)
        context.user_data.clear()

# Сохранение брони
def save_booking(name, phone, address, area, cost, datetime):
    try:
        with open(BOOKINGS_FILE, "r") as file:
            data = json.load(file)
    except FileNotFoundError:
        data = []

    booking = {
        "name": name,
        "phone": phone,
        "address": address,
        "area": area,
        "cost": cost,
        "datetime": datetime
    }
    data.append(booking)

    with open(BOOKINGS_FILE, "w") as file:
        json.dump(data, file, indent=4)

# Связаться с мастером
async def contact_master(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Написать в WhatsApp 📱", url="https://wa.me/79235194888")],
        [InlineKeyboardButton("Написать в Telegram 📲", url="https://t.me/remont42kemerovo")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("""
Для связи с мастером используйте следующие контакты:
• Телефон/WhatsApp: +7 (923) 519-48-88
• Telegram: @remont42kemerovo
""",
        reply_markup=reply_markup
    )

# О мастере
async def about_master(update: Update, context: ContextTypes.DEFAULT_TYPE):
    description = """
ГАРАНТИРУЮ КАЧЕСТВО! ОПЫТ 21 ГОД В КАЧЕСТВЕННОЙ ПОКRA
