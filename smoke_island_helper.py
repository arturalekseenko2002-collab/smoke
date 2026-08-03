from aiogram import Bot, Dispatcher, types, executor
from random import randint
import asyncio
import re
from collections import defaultdict
import logging

ORDERS_CHAT = -4635015252


BOT_TOKEN = '8492201681:AAHDyBvU06egyAch5wn0Ap6S5M8bf1ne6zo'
# BOT_TOKEN = '8113873803:AAF9iPUyz56JoLRU1B30bJUxWqRoroikLvg'
bot = Bot(BOT_TOKEN)
dp = Dispatcher(bot)

logging.basicConfig(
    level=logging.INFO,  # Можно заменить на DEBUG для более подробных логов
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def get_data(order_text):
    import re
    from collections import defaultdict

    # -----------------------------
    # Шаг 1. Парсинг исходного текста
    # -----------------------------
    try:
        order_number_match = re.search(r"Order\s+#(\d+)", order_text)
        order_number = order_number_match.group(1) if order_number_match else None
    except:
        return ''

    if not order_number:
        return ''

    # 1 строка товара:
    # 1) индекс
    # 2) название
    # 3) кол-во
    # 4) цена за 1
    # 5) цвет (опц.)
    # 6) om (опц.)
    # 7) вкус (опц., много вариантов ключевого слова)
    product_pattern = (
        r"^(\d+)\.\s+(.+?):\s+(\d+)\s+\((\d+)\s*x\s*(\d+)\)"
        r"(?:\s+Kolor:\s*(.+?))?"
        r"(?:\s+Om:\s*(\S+))?"
        r"(?:\s+(?:Smak|smak|Смак|вкус|Flavor|flavor|The\s+Taste\s+of|the\s+taste\s+of):\s+(.+))?$"
    )
    matches = re.findall(product_pattern, order_text, re.MULTILINE)

    products = []
    for m in matches:
        prod = {
            "index": int(m[0]),
            "name": m[1].strip(),
            "quantity": int(m[3]),
            "unit_price": int(m[4]),
            "price": int(m[3]) * int(m[4]),
            "color": m[5].strip() if m[5] else None,
            "om": m[6].strip() if m[6] else None,
            "flavor": m[7].strip() if m[7] else None,
        }
        products.append(prod)

    # Схлопываем полностью идентичные позиции (одинаковое имя + одинаковые вариации)
    def merge_products(prods):
        merged = {}
        for p in prods:
            key = (p['name'], p.get('color'), p.get('om'), p.get('flavor'))
            if key not in merged:
                merged[key] = p.copy()
            else:
                merged[key]['quantity'] += p['quantity']
                merged[key]['price'] += p['price']
        return list(merged.values())

    products = merge_products(products)

    # Доставка/плательщик
    shipping_method_match = re.search(r"Metod_dostawy:\s*(.+)", order_text)
    shipping_method = (shipping_method_match.group(1).strip()
                       if shipping_method_match else "Не указан")

    # Иногда в шапке встречается просто "Paczkomaty InPost" отдельной строкой — подстрахуемся
    if "Paczkomaty InPost" in order_text and shipping_method == "Не указан":
        shipping_method = "Paczkomaty InPost"

    # Сумма оплаты
    payment_match = re.search(r"Payment Amount:\s+(\d+)\s*PLN", order_text)
    payment_amount = int(payment_match.group(1)) if payment_match else 0

    # Получатель
    purchaser_name = (re.search(r"Imię_i_Nazwisko:\s*(.+)", order_text) or [None, "Не указано"])[1].strip()
    purchaser_phone = (re.search(r"Numer_telefonu:\s*(.+)", order_text) or [None, "Не указан"])[1].strip()
    if purchaser_phone.startswith('+'):
        clean_phone = '+' + re.sub(r'\D', '', purchaser_phone[1:])
    else:
        clean_phone = re.sub(r'\D', '', purchaser_phone)
    purchaser_email = (re.search(r"E-mail:\s*(.+)", order_text) or [None, "Не указан"])[1].strip()
    purchaser_city  = (re.search(r"Miasto:\s*(.+)", order_text) or [None, "Не указан"])[1].strip()

    # Код пачкомата: поддержим оба варианта ключа
    paczkomat_match = (
        re.search(r"Kod_paczkomatu:\s*(.+)", order_text) or
        re.search(r"Kod_рaczkomatu:\s*(.+)", order_text)  # с кириллической 'р'
    )
    paczkomat_code = paczkomat_match.group(1).strip() if paczkomat_match else "Не указан"

    postal_code = (re.search(r"Kod_pocztowy:\s*(.+)", order_text) or [None, ""])[1].strip()
    street      = (re.search(r"Ulica:\s*(.+)", order_text) or [None, ""])[1].strip()
    building_no = (re.search(r"Numer_budynku:\s*(.+)", order_text) or [None, ""])[1].strip()
    apt_no      = (re.search(r"Numer_lokalu:\s*(.+)", order_text) or [None, ""])[1].strip()

    # Блок адреса/доставки
    if shipping_method in ['Paczkomaty InPost', 'Paczkomat InPost']:
        shipping_data_text = (
            f"<b>Metod dostawy: Paczkomat❗️</b>\n\n"
            f"<b>Dane dla wysyłki:📝</b>\n"
            f"▫️Imię i nazwisko - {purchaser_name}\n"
            f"▫️Numer telefonu - {purchaser_phone}\n"
            f"▫️Miasto - {purchaser_city}\n"
            f"▫️Kod paczkomatu - {paczkomat_code}\n"
            # f"▫️Adres e-mail - {purchaser_email}\n"
        )
    else:
        shipping_data_text = (
            f"<b>Metod dostawy: Kurier❗️</b>\n\n"
            f"<b>Dane dla wysyłki:📝</b>\n"
            f"▫️Imię i nazwisko - {purchaser_name}\n"
            f"▫️Numer telefonu - {purchaser_phone}\n"
            f"▫️Miejscowość - {purchaser_city}\n"
            f"▫️Kod pocztowy - {postal_code}\n"
            f"▫️Ulica - {street}\n"
            f"▫️Numer budynku - {building_no}\n"
            f"▫️Numer lokalu - {apt_no}\n"
            # f"▫️Adres e-mail - {purchaser_email}\n"
        )

    # -----------------------------
    # Шаг 2. Вычисление доставки
    # -----------------------------
    if payment_amount <= 70:
        shipping_cost = 22 if shipping_method in ['Paczkomaty InPost', 'Paczkomat InPost'] else 25
    elif payment_amount <= 300:
        shipping_cost = 25
    elif payment_amount <= 500:
        shipping_cost = 30
    elif payment_amount <= 2500:
        shipping_cost = 35
    elif payment_amount <= 3000:
        shipping_cost = 45
    else:
        shipping_cost = 50

    # -----------------------------
    # Шаг 3. Разделы и "итоги по наименованию"
    # -----------------------------
    def get_section(product_name):
        section1 = [
            'HYPERBAR 70000',
            'UWIN TORNADO 60000',
            'SKE POD CKYSTAL BAR 20000',
            'MERRY MI BLADE 30000',
            'HYPERBAR 120000'
        ]
        section2 = [
            'ELF BAR ICE KING 30000',
            'ELF BAR NIC KING 30000',
            'ELF BAR SWEET KING 30000',
            'ELF BAR SOUR KING 30000',
            'ELF BAR MOON NIGHT 40000',
            'ELF BAR GH 33000',
            'ELF BAR COMBO PRO 30000',
            'ELF BAR LUSH KING 40000',
            'ELF BAR BC 45000',
            'UWIN RANDM TWINS CRYSTAL 40000',
            'ELF BAR LUSH KING PRO 40000',
            'ELF BAR BC 40000 PRO'
        ]
        section3 = [
            'ELF BAR PLANET 25000',
            'ELF BAR D3 25000',
        ]
        section4 = [
            'RANDM TORNADO 15000',
        ]
        section5 = [
            'FUNKY MONKEY 10000',
            'YOCCO CYBERPOD 12000',
            'SNOOPY SM0KE 15000',
            'MERRY MI 16000',
            'ELF BAR BC 20000',
            'VAPORESSO XROS 5 MINI',
            'CARTRIDGE XROS',
            'CARTRIDGE XROS 3ML',
            'CARTRIDGE XROS 3 ML',
            'CARTRIDGE XROS 2ML',
            'CARTRIDGE XROS 2 ML',
            'OXVA XLIM GO 2',
            'CARTRIDGE OXVA',
            'CARTRIDGE OXVA 3ML',
            'CARTRIDGE OXVA 3 ML',
            'CARTRIDGE OXVA 2ML',
            'CARTRIDGE OXVA 2 ML',
            'CARTRIDGE SKE CRYSTAL 20000',
        ]
        section6 = [
            'LIQUID EТHEREUM',
            'LIQUID ELF LIQ',
            'LIQUID HQD',
            'LIQUID VOZOL',
            'LIQUID VOZOL PRIME',
            'LIQUID PUFFY',
            'LIQUID FUMOT',
            'LIQUID YAMI',
        ]
        if product_name in section1: return 1
        if product_name in section2: return 2
        if product_name in section3: return 3
        if product_name in section4: return 4
        if product_name in section5: return 5
        if product_name in section6: return 6
        return 0

    sections = {i: [] for i in [0, 1, 2, 3, 4, 5, 6]}
    for p in products:
        sections[get_section(p['name'])].append(p)

    def fmt_line(p):
        parts = []
        if p.get('flavor'): parts.append(p['flavor'])
        if p.get('color'):  parts.append(f"Kolor: {p['color']}")
        if p.get('om'):     parts.append(f"Om: {p['om']}")
        desc = ", ".join(parts)
        return f"{p['name']} ({desc}) - {p['quantity']} x {p['unit_price']}zł" if desc else f"{p['name']} - {p['quantity']} x {p['unit_price']}zł"

    sections_str = ""
    for section_num in range(1, 7):
        section_products = sections[section_num]
        if not section_products:
            continue

        # Группировка для "TOTAL по наименованию"
        totals_by_name = defaultdict(lambda: {"qty": 0, "price": 0})
        for p in section_products:
            totals_by_name[p['name']]["qty"] += p['quantity']
            totals_by_name[p['name']]["price"] += p['price']

        # Сортируем, чтобы позиции одного наименования шли подряд
        section_products_sorted = sorted(section_products, key=lambda x: x['name'])

        lines = [f"\n\n<b>Rozdział #{section_num}</b>"]
        cur_name = None
        for p in section_products_sorted:
            # если сменилось наименование — и не первое — вывести TOTAL предыдущего
            if cur_name is not None and p['name'] != cur_name:
                lines.append(f"\n<b>TOTAL: {cur_name} - {totals_by_name[cur_name]['qty']}</b>\n————————————————————")
            # печатаем позицию
            lines.append(fmt_line(p))
            # обновляем текущее имя
            cur_name = p['name']

        # завершить TOTAL для последнего наименования
        if cur_name is not None:
            lines.append(f"\n<b>TOTAL: {cur_name} - {totals_by_name[cur_name]['qty']}</b>")

        # общий итог по разделу
        total_szt = sum(p['quantity'] for p in section_products)
        total_price = sum(p['price'] for p in section_products)
        # lines.append(f"\n<b>Total: {total_szt} szt = {total_price}zł</b>")
        #
        sections_str += "\n".join(lines)

    # -----------------------------
    # Шаг 4. Итоговое сообщение
    # -----------------------------
    final_message = f"""
<b>Dziękuję, zamowienie przyjęte!✅</b>
————————————————————
<b>Koszyk zamówienia:🛍</b>{sections_str}
————————————————————
<b>Total: {sum(p['quantity'] for p in products)} szt = {payment_amount}zł</b>
————————————————————
{shipping_data_text}
————————————————————
<b>📬Dostawa: {shipping_cost}zł</b>
<b>💰Do zapłaty: {payment_amount}+{shipping_cost}={payment_amount+shipping_cost}zł</b>
————————————————————
    """
    return final_message


@dp.message_handler(content_types=['text'])
async def text_worker(message: types.Message):
    # logging.info(f"Message from {message.from_user.id}: {message.text}")

    text = get_data(message.text)

    if text:
        # await message.answer(text, parse_mode='HTML')
        await message.bot.send_message(ORDERS_CHAT, text, parse_mode='HTML')
#
# @dp.business_message()
# async def b(message: types.Message):
#     print(message.text)
# id='U8ohonUmKUsBDwAAx5XzSZWms1w' user=User(id=837143843, is_bot=False, first_name='Артем', last_name='М', username='martem1', language_code='uk', is_premium=True, added_to_attachment_menu
# =None, can_join_groups=None, can_read_all_group_messages=None, supports_inline_queries=None, can_connect_to_business=None, has_main_web_app=None) user_chat_id=837143843 date=datetime.date
# time(2025, 3, 27, 18, 27, 54, tzinfo=TzInfo(UTC)) can_reply=False is_enabled=True



if __name__ == '__main__':
    executor.start_polling(dp)
#     a = get_data(f'''
# Order #1191198453
# 1. VAPORESSO XROS 4 MINI: 90 (1 x 90) Kolor: Camo Red
# 2. VAPORESSO XROS 4 MINI: 90 (1 x 90) Kolor: Ice Blue
# 3. VAPORESSO XROS 4 MINI: 90 (1 x 90) Kolor: Space Grey
# 4. VAPORESSO XROS 4 MINI: 90 (1 x 90) Kolor: Ice Pink
# 5. CARTRIDGE XROS 3 ML: 60 (1 x 60) Om: 0,8
# 6. CARTRIDGE XROS 3 ML: 60 (1 x 60) Om: 0,6
# 7. LIQUID HQD: 50 (1 x 50) Flavor: Banana Ice
# 8. LIQUID HQD: 50 (1 x 50) Flavor: Gummy Bear
# 9. VAPORESSO XROS 4 MINI: 90 (1 x 90) Kolor: Camo Red
# 10. LIQUID HQD: 50 (1 x 50) Flavor: Banana Ice
# 11. CARTRIDGE XROS 3 ML: 60 (1 x 60) Om: 0,8
#
# Paczkomaty InPost
# Payment Amount: 580 PLN
# Payment system: (none)
#
# Purchaser information:
# Imię_i_Nazwisko: Вдадад
# Numer_telefonu: +995 (568) 686-886
# E-mail: makarborzoi2000@gmail.com
# Metod_dostawy: Paczkomaty InPost
# Miasto: Сдсжсж
# Kod_рaczkomatu: Ажпзр
# potwierdzenie_2: yes
#
# Additional information:
# Transaction ID: 11788555:7653994344
# Block ID: rec867400902
# Form Name: Cart
# https://smoke-island.store/#tcart
# -----
# ''')
#     print(a)
