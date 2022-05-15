import os
import sys
import time
import telegram
import requests
import logging

from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logger = logging.getLogger(__name__)
handler = RotatingFileHandler(
    'my_bot.log',
    maxBytes=1048576,
    backupCount=10
)
logger.addHandler(handler)


def send_message(bot, message):
    """Функция отправки сообщения в Телеграм."""
    logger.info("Начинаем отправку сообщения в Telegram")
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception as error:
        logger.error(f'Ошибка {error} при отправке сообщения')
    else:
        logger.info("Сообщение отправлено")

def get_api_answer(current_timestamp) -> dict:
    """Делает запрос к API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {"from_date": timestamp}
    try:
        logger.info("отправляем api-запрос")
        response = requests.get(
            ENDPOINT, params=params, headers=HEADERS
        )
    except ValueError as error:
        raise error
    error_message = (
        f'Проблемы соединения с сервером'
        f'ошибка {response.status_code}'
    )
    if response.status_code == requests.codes.ok:
        return response.json()
    raise TypeError(error_message)


def check_response(response):
    """Проверяем ответ API на корректность."""
    err_key = 'Ошибка: homeworks не найден в ответе'
    err_index = 'Ошибка: Домашняя работа не найдена'
    if not isinstance(response, dict):
        raise TypeError("api answer is not dict")
    try:
        homework_list = response["homeworks"]
    except KeyError:
        raise KeyError(err_key)
    try:
        homework_list[0]
    except IndexError:
        raise IndexError(err_index)
    return homework_list


def parse_status(homework) -> str:
    """Извлекаем из информации о домашней работе статус этой работы."""
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')
    if 'status' not in homework:
        raise Exception('Отсутствует ключ "status" в ответе API')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES:
        raise Exception(f'Неизвестный статус работы: {homework_status}')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens() -> bool:
    """Функция проверяющая доступность переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствуют переменные окружения. Работа программы'
                        ' будет завершена.')
        sys.exit(1)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time()) - RETRY_TIME
    status = None
    error_work = None
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            homework_status = homework.get("status")
            if homework_status != status:
                status = homework_status
                message = parse_status(homework)
                send_message(bot, message)
            else:
                logger.info("Статус работы не изменился.")
            current_timestamp = int(time.time())
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if message != error_work:
                error_work = message
                send_message(bot, message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
