# Описание
Приложение для платформы Google App Engine, которое через ботов пересылает сообщения между чатами Telegram и VK. Еще может присылать уведомления в Telegram о новых постах и комментариях в группе VK.

# Чаты
Изначально разрабатывалось для расширения охвата существующего Telegram-чата путем присоединения VK-чата (для тех, кто не хочет или не может пользоваться Телеграмом). Также поможет, если вам по необходимости нужно сидеть в каком-нибудь VK-чате, но пользоваться официальным клиентом вам невыносимо. Настраиваете ботов и пишете из любимой тележки :)

## Что реализовано

### Текстовые сообщения
Поддерживается в обе стороны

### Изображения
Поддерживается в обе стороны

### Cтикеры
Поддерживается в обе стороны

### Локейшены
Поддерживается в обе стороны

### Контакты
* TG -> VK: поддерживается
* VK -> TG: нет такой функциональности

### Реплаи (ответы)
* TG -> VK: так как текущий VK Bot API не позволяет делать реплаи на сообщения, цитируемый текст помещается в начале сообщения и визуально выделяется с помощью эмоджи (форматирования текста в VK нет).
* VK -> TG: отображается нативно, как обычный ответ в Telegram. Для определения соответствия id сообщений в обоих чатах используется небольшая хитрость с сохранением контрольной суммы и времени сообщения (получать id отправленных сообщений VK также не позволяет).

### Редактирование/удаление сообщений
К сожалению, практически ничего нельзя реализовать из-за ограничений VK Bot API. Единственное, если в VK отредактировали текстовое сообщение, а потом ответили на него, приложение понимает, что было изменение, и обновит исходное сообщение в TG.

### Видео, файлы, музыка
Не реализовано

# Уведомления о постах и комментариях
Мгновенные уведомления о новых постах и комментариях в группах VK через Callback API. Из вложений поддерживаются только фото.

# Настройка
Отредактируйте config.py:

`TGBOTTOKEN` — токен бота в Telegram

`TGBOTUSERNAME` — юзернейм бота в Telegram

`VKAPIVER` — версия VK API

`VKTOKEN` — ключ доступа VK (access_token). См.: https://vk.com/dev/access_token

`VKGROUPTOKEN` — ключ доступа сообщества (VK-бот по сути является сообществом). См.: https://vk.com/dev/access_token

`VKMYID` — id вашего VK-аккаунта. Необязательный параметр.

`TIMETRESHOLD` — на текущий момент должен быть равен 1

`confirmation` — dict, в котором ключ — это id группы VK, а значение — строка, которую должен вернуть сервер при настройке вебхука в группе.

`wallpost` — dict, в котором ключ — это id группы VK, а значение — id чата в Telegram, куда будут приходить уведомления о новых постах в этой группе. Все id — целые числа.

`comment` — dict, в котором ключ — это id группы VK, а значение — id чата в Telegram, куда будут приходить уведомления о новых комментариях в этой группе. Все id — целые числа.

`tg2vkid` — dict, в котором ключ — это id чата в Telegram, а значение — id чата в VK (не для вас, а для VK-бота), между которыми будет пересылка сообщений. Все id — целые числа.

 # Развертывание
 Подробно расписать все сложно, поэтому только кратко, возможно, некоторые шаги забыл. Если что-то непонятно, придется погуглить 🤷‍♂️
  * Создать бота в Telegram, включить бота в чат, сделать администратором чата
* Создать сообщество в VK (можно закрытое), включить сообщения сообщества, включить возможности ботов и добавление сообщества в беседы, добавить сообщество в чат, сделать администратором
* У сообщества VK включить Callback API (версия не ниже 5.80), настроить типы событий (сообщения, посты, комментарии)
* Отредактировать config.py
* Создать приложение в Google App Engine, задеплоить код
* Настроить вебхук телеграм-бота на адрес https://your_application.appspot.com/tghook
* Настроить вебхук (Callback API) сообщества VK на адрес https://your_application.appspot.com
* После настройки вебхуков можно смотреть логи Google App Engine, там будут все приходящие json'ы в удобочитаемом виде, в них можно найти id чатов, пользователей и т.д.