#!/usr/bin/python3

import logging
import telebot
import threading
import time
import json
import random
import argparse
from datetime import datetime, timezone, timedelta

parser = argparse.ArgumentParser(prog='Media Server')
parser.add_argument('-l', '--log-path', default=None)
args = parser.parse_args()

logging.basicConfig(filename=args.log_path, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', force=True)

logger = logging.getLogger("engine")
logger.setLevel(logging.DEBUG)

MOSCOW_TIMEZONE = timezone(timedelta(hours=3))
TIME_FORMAT="%Y-%m-%dT%H:%M:%S"
MIN_TIME=(datetime.min + timedelta(days=400000)).replace(tzinfo=timezone.utc).astimezone(MOSCOW_TIMEZONE)

token_path = "token"
with open(token_path, 'r') as f:
    API_TOKEN = f.readline()[:-1]

bot = telebot.TeleBot(API_TOKEN)

# Список предложений и соответствующих им фотографий
with open("sentences.json", 'r') as f:
    sentences_with_photos = json.load(f)

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
        to_choose = [s for s in self.all_sentences if s["index"] not in self.sent_sentences[chat_id]]
        if len(to_choose) == 0:
            return None
        return random.choice(to_choose)

    def send_sentence_for_client(self, sentence_index, chat_id):
        self.sent_sentences[chat_id].append(sentence_index)
        self.__dump__()


def wait(t:int):
    for i in range(t):
        time.sleep(1)
        yield i

class ChatsManager:
    time_delta=timedelta(seconds=10)
    last_send_message_time = "last_send_message_time.json"

    def __init__(self, bot):
        with open(ChatsManager.last_send_message_time, 'r') as f:
            self.last_send_message_time = {id:datetime.strptime(t, TIME_FORMAT).replace(tzinfo=MOSCOW_TIMEZONE) for id, t in json.load(f).items()}
        self.lock = threading.Lock()
        self.bot = bot
        self.sentenses_manager = SentensesManager()

    def __dump__(self):
        with open(ChatsManager.last_send_message_time, 'w') as f:
            json.dump({id:t.strftime(TIME_FORMAT) for id, t in self.last_send_message_time.items()}, f)

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
            for i in wait(5):
                if self.has_any_to_send():
                    break
            self.send_messages()

    def add_chat_id(self, chat_id):
        self.lock.acquire()
        chat_id_str = str(chat_id)
        if chat_id_str not in self.last_send_message_time:
            self.last_send_message_time[chat_id] = MIN_TIME
            self.__dump__()
        self.lock.release()

    def send_message(self, chat_id):
        item = self.sentenses_manager.get_sentence_for_client(chat_id)
        if item is None:
            logger.info("messages ended for " + str(chat_id))
            self.last_send_message_time[chat_id] = datetime.max.replace(tzinfo=MOSCOW_TIMEZONE)
            self.__dump__()
            return

        # logger.info("Server started, listening on " + port)
        with open(item["photo"], 'rb') as photo:
            self.bot.send_photo(chat_id, photo, caption=item["text"])
        logger.info("sending message " + str(chat_id) + " " + str(item["index"]) + " " +  item["text"])
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

#TODO  добавить first message time

manager = ChatsManager(bot)

manager.start()
# Обработчик команды /start
@bot.message_handler(commands=['start'])
def send_welcome(message):

    bot.reply_to(message, "Привет, Таня")
    manager.add_chat_id(message.chat.id)


# Запуск бота
bot.polling(non_stop=True)
