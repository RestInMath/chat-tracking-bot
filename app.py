from flask import Flask, request
import telepot
from urllib3 import ProxyManager
from logging import getLogger
import os
from dotenv import load_dotenv
from typing import Tuple

# business logic settings
KEYWORDS = ["keyword_example"]
WHITELIST = []
KEYWORDS_FILE_PATH = "mysite/keywords.txt"
WHITELIST_FILE_PATH = "mysite/whitelist.txt"
BASE_CHAT_ID_FILEPATH = "mysite/base_chat.txt"
BASE_CHAT_ID = None

app = Flask(__name__)
logger = getLogger(__name__)


def load_keywords() -> None:
    global KEYWORDS
    with open(KEYWORDS_FILE_PATH, 'r') as file:
        KEYWORDS = file.read().splitlines()


def load_whitelist() -> None:
    global WHITELIST
    with open(WHITELIST_FILE_PATH, 'r') as file:
        WHITELIST = file.read().splitlines()


def load_base_chat() -> None:
    global BASE_CHAT_ID
    with open(BASE_CHAT_ID_FILEPATH, 'r') as file:
        BASE_CHAT_ID = file.read()


def set_configuration() -> Tuple:
    global TOKEN, SECRET, PA_NAME
    TOKEN = os.getenv("TOKEN")
    SECRET = os.getenv("SECRET")
    PA_NAME = os.getenv("PA_NAME")

    return SECRET, TOKEN, PA_NAME


load_keywords()
load_whitelist()
load_base_chat()
env_res = load_dotenv()
logger.error("loading env res: %s", env_res)
SECRET, TOKEN, PA_NAME = set_configuration()


def get_text_from_message(message):
    return message.get("text", {})


# all functions should have 'bot', 'chat_id' and 'text' args
# mb add 'show_groups' and 'save_group' funcs
# TODO: add whitelist
def show_keywords(bot, chat_id, text):
    load_keywords()
    keywords_list = "\n".join(KEYWORDS)
    bot.sendMessage(chat_id, keywords_list)


def set_keywords(bot, chat_id, text):
    # TODO: add logic
    command_length = 14
    keywords_list = text[command_length:].lower()
    with open(KEYWORDS_FILE_PATH, 'w') as file:
        file.write(keywords_list)
    load_keywords()
    bot.sendMessage(chat_id, f"New keywords list:\n{keywords_list}")


def add_keywords(bot, chat_id, text):
    command_length = 14
    keywords_list = '\n'+text[command_length:].lower()
    with open(KEYWORDS_FILE_PATH, 'a') as file:
        file.write(keywords_list)
    load_keywords()
    new_list = '\n'.join(KEYWORDS)
    bot.sendMessage(chat_id, f"New keywords list:\n{new_list}")


def show_whitelist(bot, chat_id, text):
    whitelist = set('\n'.join(WHITELIST))
    bot.sendMessage(chat_id, f"Whitelist:\n{whitelist}")


def set_whitelist(bot, chat_id, text):
    command_length = 15
    new_whitelist = text[command_length:]
    with open(WHITELIST_FILE_PATH, 'w') as file:
        file.write(new_whitelist)
    load_whitelist()
    bot.sendMessage(chat_id, f"New whitelist:\n{new_whitelist}")


def make_base_chat(bot, chat_id, text):
    global BASE_CHAT_ID
    BASE_CHAT_ID = chat_id
    with open(BASE_CHAT_ID_FILEPATH, 'w') as file:
        file.write(str(chat_id))
    bot.sendMessage(chat_id, "This is base chat now")


def check_message(bot, chat_id, message):
    text = message.get("text", "").lower()
    for keyword in KEYWORDS:
        if keyword in text:
            if "chat" in message and "username" in message["chat"]:
                # send link to the message if possible
                chat_name = message["chat"]["username"]
                message_id = message["message_id"]
                link = f"https://t.me/{chat_name}/{message_id}"
                bot.sendMessage(BASE_CHAT_ID, link)
            else:
                # send text of the message
                bot.sendMessage(BASE_CHAT_ID, f"В группе {chat_id} было сообщение: {text}")


def user_in_whitelist(message, func):
    user_info = message.get("from", {})
    user_id = user_info.get("id", None)
    username = user_info.get("username", None)
    whitelisted_user = str(user_id) in WHITELIST or str(username) in WHITELIST if (user_id or username) else False

    logger.info(f"user in whitelist: {whitelisted_user}")
    if not whitelisted_user:
        logger.info(f"user with id {user_id}, and username '{username}' tried to use {func.__name__} command. "
                    "User is not whitelisted")
        return False
    else:
        logger.info(f"user with id {user_id}, and username '{username}' used {func.__name__} command")
        return True


def help_message(bot, chat_id, help_info):
    funcs_info_dict = {
        "/show_keywords": "Show current list of keywords",
        "/set_keywords": "Set new list of keywords.\nFormat:\n"
                         "'/set_keywords\nkeyword1\nkeyword2'",
        "/add_keywords": "Add some words to the current keywords list.\nFormat:\n"
                         "'/add_keywords\nkeyword\nkeyword'",
        "/show_whitelist": "Show current list of whitelisted users",
        "/set_whitelist": "Set new list of whitelisted users.\nFormat:\n"
                          "'/set_whitelist\nusername or user_id\nusername or user_id'",
        "/make_this_chat_base": "Make this chat base. All messages with keywords will be directed here",
        "/help": "Show this message",
    }
    help_info = "Welcome to the chat tracking bot. Here is a command list:\n"
    for func_name, func_desc in funcs_info_dict.items():
        help_info += f"{func_name}: {func_desc}\n\n"
    bot.sendMessage(chat_id, help_info)


def parse_command(bot, chat_id, message):
    text = message.get("text", "")
    funcs_dict = {
        "/show_keywords": show_keywords,
        "/set_keywords": set_keywords,
        "/add_keywords": add_keywords,
        "/show_whitelist": show_whitelist,
        "/set_whitelist": set_whitelist,
        "/make_this_chat_base": make_base_chat,
        "/help": help_message,
    }

    logger.info(f"message in chat: {chat_id}")
    for command, func in funcs_dict.items():
        if text.startswith(command):
            if user_in_whitelist(message, func):
                func(bot, chat_id, text)
            return

    check_message(bot, chat_id, message)


def get_tg_bot():
    # proxy settings
    proxy_url = "http://proxy.server:3128"
    telepot.api._pools = {
        'default': ProxyManager(proxy_url=proxy_url, num_pools=3, maxsize=10, retries=False, timeout=30),
    }
    telepot.api._onetime_pool_spec = (
        ProxyManager, dict(proxy_url=proxy_url, num_pools=1, maxsize=1, retries=False, timeout=30))

    webhook_url = f"https://{PA_NAME}.pythonanywhere.com/{SECRET}"
    logger.error("webhook: %s", webhook_url)
    bot = telepot.Bot(TOKEN)
    bot.setWebhook(webhook_url, max_connections=1)

    load_keywords()

    return bot


@app.route('/{}'.format(SECRET), methods=["POST"])
def telegram_webhook():
    bot = get_tg_bot()

    update = request.get_json()
    if "message" in update:
        chat_id = update["message"]["chat"]["id"]
        message = update["message"]
        if "text" in message:
            parse_command(bot, chat_id, message)

    return "OK"
