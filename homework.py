import os
import time
import logging
import requests
import http
from dotenv import load_dotenv
from telebot import TeleBot, apihelper

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD: int = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()],
)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    if not all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        missing_tokens = [
            name for name in [
                'PRACTICUM_TOKEN',
                'TELEGRAM_TOKEN',
                'TELEGRAM_CHAT_ID'
            ]
            if globals().get(name) is None
        ]
        logging.critical(
            f'Отсутствуют обязательные переменные окружения: '
            f'{", ".join(missing_tokens)}'
        )
        raise ValueError(
            f'Отсутствуют обязательные переменные окружения: '
            f'{", ".join(missing_tokens)}'
        )


def send_message(bot, message):
    """Отправляет сообщение в Telegram и логирует результат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Бот отправил сообщение: "{message}"')
    except apihelper.ApiException as error:
        logging.error(f'Сбой при отправке сообщения в Telegram: {error}')


def handle_api_error(response):
    """Проверяет статус ответа API и выбрасывает исключение в случае ошибки."""
    if response.status_code != http.HTTPStatus.OK:
        error_message = (
            f'API вернул неожиданный статус: {response.status_code}'
        )
        logging.error(error_message)
        raise requests.HTTPError(error_message)


def get_api_answer(timestamp):
    """Делает запрос к API и возвращает ответ."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
        handle_api_error(response)
        return response.json()
    except requests.RequestException as err:
        error_message = f'Ошибка запроса к API: {err}'
        logging.error(error_message)
        raise AssertionError(error_message)


def check_response(response):
    """Проверяет ответ API на наличие необходимых ключей."""
    if not isinstance(response, dict):
        logging.error('Ответ API должен быть словарем')
        raise TypeError('Ответ API должен быть словарем')

    if 'homeworks' not in response:
        logging.error('Отсутствуют ключи в ответе API')
        raise KeyError('Отсутствуют ключи в ответе API')

    homeworks = response['homeworks']

    if not isinstance(homeworks, list):
        logging.error('Данные под ключом "homeworks" должны быть списком')
        raise TypeError('Данные под ключом "homeworks" должны быть списком')

    return homeworks


def parse_status(homework):
    """Извлекает статус домашней работы и возвращает сообщение."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if homework_name is None:
        logging.error('Отсутствует ключ "homework_name" в домашней работе')
        raise KeyError('Отсутствует ключ "homework_name" в домашней работе')

    verdict = HOMEWORK_VERDICTS.get(homework_status)

    if verdict is None:
        logging.error(f'Неожиданный статус домашней работы: {homework_status}')
        raise ValueError(f'Неожиданный статус: {homework_status}')

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = TeleBot(TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)

            if homeworks:
                for homework in homeworks:
                    message = parse_status(homework)
                    send_message(bot, message)

            else:
                logging.debug('Нет новых статусов')

            time.sleep(RETRY_PERIOD)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            logging.error(message)
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
