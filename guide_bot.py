import random

import sqlalchemy
from sqlalchemy import func
from sqlalchemy.orm import sessionmaker
from telebot import types, TeleBot, custom_filters
from telebot.storage import StateMemoryStorage
from telebot.handler_backends import State, StatesGroup
from models import create_tables, Users, PersonalDict, EnglishDict

print('Start telegram bot...')

state_storage = StateMemoryStorage()
token_bot = ''
bot = TeleBot(token_bot, state_storage=state_storage)

buttons = []

DSN = 'postgresql://postgres:postgres@localhost:5432/englishlessons'
engine = sqlalchemy.create_engine(DSN)
Session = sessionmaker(bind=engine)
create_tables(engine)
session = Session()
if not session.query(EnglishDict).first():
    try:
        words_pairs = [
            ("Dog", "Собака"),
            ("Cat", "Кошка"),
            ("Horse", "Лошадь"),
            ("Pig", "Свинья"),
            ("Cow", "Корова"),
            ("Elephant", "Слон"),
            ("Ape", "Обезьяна"),
            ("Rhino", "Носорог"),
            ("Hawk", "Ястреб"),
            ("Wolf", "Волк"),
            ("Tiger", "Тигр"),
            ("Lion", "Лев"),
        ]
        word_pairs = [EnglishDict(english_word=eng, russian_word=rus) for eng, rus in words_pairs]
        session.add_all(word_pairs)
        session.commit()
    except Exception as e:
        session.rollback()
        print(e)
    finally:
        session.close()


def show_hint(*lines):
    return '\n'.join(lines)


def show_target(data):
    return f"{data['target_word']} -> {data['translate_word']}"


class Command:
    ADD_WORD = 'Добавить слово ➕'
    DELETE_WORD = 'Удалить слово🔙'
    NEXT = 'Дальше ⏭'


class MyStates(StatesGroup):
    target_word = State()
    translate_word = State()
    another_words = State()
    waiting_english = State()
    waiting_russian = State()


@bot.message_handler(commands=['cards', 'start'])
def create_cards(message):
    session = Session()
    uid = message.from_user.id
    try:
        user = session.query(Users).filter_by(user_id=uid).first()
        if not user:
            user = Users(user_id=uid)
            session.add(user)
            session.flush()
            bot.send_message(message.chat.id, "Hello, stranger, let's study English...")
            default_words = session.query(EnglishDict).limit(12).all()
            for words in default_words:
                link = PersonalDict(user_id=user.id, word_id=words.id)
                session.add(link)
        session.commit()
        markup = types.ReplyKeyboardMarkup(row_width=2)
        global buttons
        buttons = []
        random_word = session.query(PersonalDict).filter_by(user_id=user.id).order_by(func.random()).first()
        if not random_word:
            bot.send_message(message.chat.id, "В вашем словаре пока нет слов. Добавьте их через /add.")
            return
        word = session.query(EnglishDict).filter_by(id=random_word.word_id).first()
        target_word = word.english_word   # брать из БД
        translate = word.russian_word  # брать из БД
        target_word_btn = types.KeyboardButton(target_word)
        buttons.append(target_word_btn)
        others = session.query(EnglishDict.english_word).join(PersonalDict).filter(
            PersonalDict.user_id == user.id,
            EnglishDict.english_word != target_word
        ).order_by(func.random()).limit(3).all()
        others = [w[0] for w in others]  # брать из БД
        other_words_btns = [types.KeyboardButton(word) for word in others]
        buttons.extend(other_words_btns)
        random.shuffle(buttons)
        next_btn = types.KeyboardButton(Command.NEXT)
        add_word_btn = types.KeyboardButton(Command.ADD_WORD)
        delete_word_btn = types.KeyboardButton(Command.DELETE_WORD)
        buttons.extend([next_btn, add_word_btn, delete_word_btn])
        markup.add(*buttons)
        greeting = f"Выбери перевод слова:\n🇷🇺 {translate}"
        bot.send_message(message.chat.id, greeting, reply_markup=markup)
        bot.set_state(message.from_user.id, MyStates.target_word, message.chat.id)
        with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            data['target_word'] = target_word
            data['translate_word'] = translate
            data['other_words'] = others
    except Exception as e:
        session.rollback()
        print(e)
        bot.send_message(message.chat.id, "Что-то пошло не так")
    finally:
        session.close()


@bot.message_handler(func=lambda message: message.text == Command.NEXT)
def next_cards(message):
    create_cards(message)


@bot.message_handler(func=lambda message: message.text == Command.DELETE_WORD)
def delete_word(message):
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        session = Session()
        try:
            print(data['target_word'])  # удалить из БД
            target_word = data['target_word']
            print(target_word)
            user = session.query(Users).filter_by(user_id=message.from_user.id).first()
            word = session.query(EnglishDict).filter_by(english_word=target_word).first()
            if not user or not word:
                bot.send_message(message.chat.id, "Не удалось найти слово или пользователя.")
                return
            deleted = session.query(PersonalDict)\
                .filter_by(
                user_id=user.id,
                word_id=word.id
            ).delete()
            session.commit()
            if deleted > 0:
                bot.send_message(message.chat.id, f"Слово {target_word} успешно удалено")
            else:
                bot.send_message(message.chat.id, "Ошибка в удалении")
        except Exception as e:
            session.rollback()
            print(e)
            bot.send_message(message.chat.id, "Oшибка при удалении.")
        finally:
            session.close()


@bot.message_handler(func=lambda message: message.text == Command.ADD_WORD)
def add_word(message):
    bot.send_message(message.chat.id, "Введите английское слово:")
    bot.set_state(message.from_user.id, MyStates.waiting_english, message.chat.id)


@bot.message_handler(state=MyStates.waiting_english)
def add_word_english(message):
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['new_english'] = message.text.strip()
    bot.send_message(message.chat.id, "Теперь введите перевод на русский:")
    bot.set_state(message.from_user.id, MyStates.waiting_russian, message.chat.id)


@bot.message_handler(state=MyStates.waiting_russian)
def add_word_russian(message):
    russian = message.text.strip()
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        english = data.get('new_english')
    if not english:
        bot.send_message(message.chat.id, "Ошибка: не удалось восстановить английское слово.")
        bot.delete_state(message.from_user.id, message.chat.id)
        return

    session = Session()
    try:
        user = session.query(Users).filter_by(user_id=message.from_user.id).first()
        if not user:
            user = Users(user_id=message.from_user.id)
            session.add(user)
            session.flush()
        word = session.query(EnglishDict).filter_by(english_word=english).first()
        if not word:
            word = EnglishDict(english_word=english, russian_word=russian)
            session.add(word)
            session.flush()
        else:
            if word.russian_word != russian:
                bot.send_message(
                    message.chat.id,
                    f"Слово '{english}' уже в словаре с переводом '{word.russian_word}'"
                )
                return

        existing = session.query(PersonalDict).filter_by(
            user_id=user.id,
            word_id=word.id
        ).first()

        if existing:
            bot.send_message(message.chat.id, "Слово уже в словаре")
        else:
            link = PersonalDict(user_id=user.id, word_id=word.id)
            session.add(link)
            session.commit()
            bot.send_message(
                message.chat.id,
                f"Слово '{english} и его перевод – {russian}' добавлены в ваш словарь!"
            )
    except Exception as e:
        session.rollback()
        print(e)
        bot.send_message(message.chat.id, "Oшибка при добавлении слова.")
    finally:
        session.close()
        create_cards(message)


@bot.message_handler(func=lambda message: True, content_types=['text'])
def message_reply(message):
    text = message.text
    markup = types.ReplyKeyboardMarkup(row_width=2)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        target_word = data.get('target_word')
        if target_word is None:
            bot.send_message(message.chat.id, "Введите /start")
            return
        if text == target_word:
            hint = show_target(data)
            hint_text = ["Отлично!❤", hint]
            next_btn = types.KeyboardButton(Command.NEXT)
            add_word_btn = types.KeyboardButton(Command.ADD_WORD)
            delete_word_btn = types.KeyboardButton(Command.DELETE_WORD)
            buttons.extend([next_btn, add_word_btn, delete_word_btn])
            hint = show_hint(*hint_text)
        else:
            for btn in buttons:
                if btn.text == text:
                    btn.text = text + '❌'
                    break
            hint = show_hint("Допущена ошибка!",
                             f"Попробуй ещё раз вспомнить слово 🇷🇺{data['translate_word']}")

    markup.add(*buttons)
    bot.send_message(message.chat.id, hint, reply_markup=markup)


bot.add_custom_filter(custom_filters.StateFilter(bot))

bot.infinity_polling(skip_pending=True)
