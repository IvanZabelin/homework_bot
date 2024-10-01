import os
import time
import logging
import http

import requests
from dotenv import load_dotenv
from telebot import TeleBot, apihelper

load_dotenv()

PRACTICUM_TOKEN: str = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN: str = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID: str = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD: int = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения."""
    missing_tokens = [
        name for name, token in {
            'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
            'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
            'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
        }.items() if token is None
    ]

    if missing_tokens:
        logging.critical(
            'Отсутствуют обязательные переменные окружения: '
            f'{", ".join(missing_tokens)}'
        )
        raise ValueError(
            'Отсутствуют обязательные переменные окружения: '
            f'{", ".join(missing_tokens)}'
        )


def send_message(bot, message):
    """Отправляет сообщение в Telegram."""
    logging.debug(f'Попытка отправить сообщение: "{message}"')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Бот успешно отправил сообщение: "{message}"')
    except apihelper.ApiException as error:
        logging.error(f'Сбой при отправке сообщения в Telegram: {error}')


def handle_api_error(response):
    """Проверяет статус ответа API и выбрасывает исключение в случае ошибки."""
    if response.status_code != http.HTTPStatus.OK:
        raise requests.HTTPError(
            f'API вернул неожиданный статус: {response.status_code}'
        )


def get_api_answer(timestamp):
    """Делает запрос к API и возвращает ответ."""
    params = {'from_date': timestamp}
    logging.debug(f'Попытка сделать запрос к API с параметрами: {params}')
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
        handle_api_error(response)
        logging.debug(
            'Успешный запрос к API.'
            f' Статус код: {response.status_code}'
        )
        return response.json()
    except requests.RequestException as err:
        raise AssertionError(
            f'Ошибка запроса к API: {err}. Параметры: {params}, заголовки: '
            f'{HEADERS}'
        )


def check_response(response):
    """Проверяет ответ API на наличие необходимых ключей."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API должен быть словарем')

    if 'homeworks' not in response:
        raise KeyError('Отсутствуют ключи в ответе API')

    homeworks = response['homeworks']

    if not isinstance(homeworks, list):
        raise TypeError('Данные под ключом "homeworks" должны быть списком')

    return homeworks


def parse_status(homework):
    """Извлекает статус домашней работы и возвращает сообщение."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if homework_name is None:
        raise KeyError('Отсутствует ключ "homework_name" в домашней работе')

    verdict = HOMEWORK_VERDICTS.get(homework_status)

    if verdict is None:
        raise ValueError(f'Неожиданный статус: {homework_status}')

    return (
        f'Изменился статус проверки работы "{homework_name}". {verdict}'
    )


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

        except Exception as error:
            logging.error(f'Сбой в работе программы: {error}')
            send_message(bot, f'Сбой в работе программы: {error}')
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    # Настройка логирования
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[logging.StreamHandler()],
    )
    main()
