#!/usr/bin/python3

import logging
import telebot
import threading
import time
import json
import sys
import random
import argparse
from datetime import datetime, timezone, timedelta

parser = argparse.ArgumentParser(prog='tanya_birthday')
parser.add_argument('-l', '--log-path', default=None)
args = parser.parse_args()

logging.basicConfig(filename=args.log_path, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', force=True)

logger = logging.getLogger("tanya_birthday")
logger.setLevel(logging.DEBUG)

MOSCOW_TIMEZONE = timezone(timedelta(hours=3))
TIME_FORMAT="%Y-%m-%dT%H:%M:%S"
MIN_TIME=(datetime.min + timedelta(days=400000)).replace(tzinfo=timezone.utc).astimezone(MOSCOW_TIMEZONE)
MAX_TIME=datetime(year=2054, month=7, day=26, hour=16, minute=5).replace(tzinfo=timezone.utc).astimezone(MOSCOW_TIMEZONE)
TIMEOUT=120 # default 30

token_path = "token"
with open(token_path, 'r') as f:
    API_TOKEN = f.readline()[:-1]

class MyExceptionHandler(telebot.ExceptionHandler):
    def handle(exception):
        print(datetime.now(), repr(exception), file=sys.stderr, flush=True)
        return True

bot = telebot.TeleBot(API_TOKEN, exception_handler=MyExceptionHandler)

def get_date():
    return str(datetime.now(MOSCOW_TIMEZONE).date())


class SentensesManager:
    sent_sentences = "sent_sentences.json"
    all_sentences = "sentences.json"
    def __init__(self):
        with open(SentensesManager.sent_sentences, 'r') as f:
            self.sent_sentences = json.load(f)
        with open(SentensesManager.all_sentences, 'r') as f:
            self.all_sentences = json.load(f)

    def __dump__(self):
        with open(SentensesManager.sent_sentences, 'w') as f:
            json.dump(self.sent_sentences, f)

    def get_sentence_for_client(self, chat_id):
        if chat_id not in self.sent_sentences:
            self.sent_sentences[chat_id] = list()
        date = get_date()
        to_choose = [item for item in self.all_sentences if item["index"] not in self.sent_sentences[chat_id] and ("date" not in item or item["date"] <= date)]
        today_sentences=[item for item in to_choose if "date" in item and item["date"] == date]
        if len(today_sentences) != 0:
            return random.choice(today_sentences)

        if len(to_choose) == 0:
            return None
        return random.choice(to_choose)

    def send_sentence_for_client(self, sentence_index, chat_id):
        self.sent_sentences[chat_id].append(sentence_index)
        self.__dump__()

class ChatsManager:
    # time_delta=timedelta(seconds=5)
    time_delta=timedelta(days=1)
    last_send_message_time = "last_send_message_time.json"
    chat_meta = "chat_meta.json"
    # first_message_time=datetime(year=2024, month=7, day=26, hour=16, minute=5).replace(tzinfo=MOSCOW_TIMEZONE)
    first_message_time=None

    def __init__(self, bot):
        with open(ChatsManager.last_send_message_time, 'r') as f:
            self.last_send_message_time = {id:datetime.strptime(t, TIME_FORMAT).replace(tzinfo=MOSCOW_TIMEZONE) for id, t in json.load(f).items()}
        with open(ChatsManager.chat_meta, 'r') as f:
            self.chat_meta = json.load(f)
        self.lock = threading.Lock()
        self.bot = bot
        self.sentenses_manager = SentensesManager()

    def __dump__(self):
        with open(ChatsManager.last_send_message_time, 'w') as f:
            json.dump({id:t.strftime(TIME_FORMAT) for id, t in self.last_send_message_time.items()}, f)
        with open(ChatsManager.chat_meta, 'w') as f:
            json.dump(self.chat_meta, f)

    def has_any_to_send(self):
        self.lock.acquire()
        for time in self.last_send_message_time.values():
            if time < datetime.now(MOSCOW_TIMEZONE):
                self.lock.release()
                return True
        self.lock.release()
        return False

    def start(self):
        self.thread = threading.Thread(target=self.__run_loop__)
        self.thread.start()

    def __run_loop__(self):
        while True:
            time.sleep(1)
            if self.has_any_to_send():
                self.send_messages()

    def add_chat_id(self, chat_id, from_user):
        self.lock.acquire()
        chat_id_str = str(chat_id)
        if chat_id_str not in self.last_send_message_time:
            logger.info(f"adding user {from_user.id} {from_user.first_name} {from_user.last_name} {from_user.username}")
            self.last_send_message_time[chat_id_str] = ChatsManager.first_message_time if ChatsManager.first_message_time is not None else  MIN_TIME
            self.chat_meta[chat_id_str] = {"first_name":from_user.first_name, "last_name":from_user.last_name, "username":from_user.username, "blocked":False}
            self.__dump__()
        else:
            logger.info(f"user pressed start {from_user.id} {from_user.first_name} {from_user.last_name} {from_user.username}")

        self.lock.release()

    def send_message(self, chat_id):
        item = self.sentenses_manager.get_sentence_for_client(chat_id)
        if item is None:
            logger.info("messages ended for " + str(chat_id))
            self.last_send_message_time[chat_id] = datetime.now(MOSCOW_TIMEZONE)
            self.__dump__()
            return

        with open(item["photo"], 'rb') as photo:
            try:
                self.bot.send_photo(chat_id, photo, caption=item["text"], timeout=TIMEOUT)
            except telebot.apihelper.ApiTelegramException as e:
                if e.error_code == 403 and "bot was blocked by the user" in e.description:
                    logger.error("bot was blocked by " + str(chat_id) + " \t" + str(self.chat_meta[str(chat_id)])+ " \terror: " + str(e))
                    self.last_send_message_time[chat_id] = MAX_TIME
                    self.chat_meta[str(chat_id)]["blocked"] = True
                    self.__dump__()
                else:
                    logger.error("telebot err: failed to send " + str(chat_id) + " " + str(item["index"]) + " " +  item["text"].replace('\n', '\\n') + " \terror: " + str(e) + repr(e))
                return
            except Exception as e:
                logger.error("failed to send " + str(chat_id) + " " + str(item["index"]) + " " +  item["text"].replace('\n', '\\n') + " \terror: " + str(e))
                return
        logger.info("sending message " + str(chat_id) + " " + str(item["index"]) + " " +  item["text"].replace('\n', '\\n'))
        self.sentenses_manager.send_sentence_for_client(item["index"], chat_id)
        self.last_send_message_time[chat_id] = datetime.now(MOSCOW_TIMEZONE)
        self.__dump__()

    def send_messages(self):
        self.lock.acquire()
        for chat_id, time in self.last_send_message_time.items():
            if time + ChatsManager.time_delta >= datetime.now(MOSCOW_TIMEZONE):
                continue
            self.send_message(chat_id)
        self.lock.release()


manager = ChatsManager(bot)

manager.start()
# Обработчик команды /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, f"Привет, {message.from_user.username}")
    manager.add_chat_id(message.chat.id, message.from_user)


# Запуск бота
bot.polling(non_stop=True)
