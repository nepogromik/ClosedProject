#!/bin/bash

# Скрипт установки Gallery Bot для Ubuntu Server
# Автоматическая установка всех зависимостей и настройка

set -e  # Остановка при ошибке

echo "=================================="
echo "  Gallery Bot - Установка"
echo "=================================="
echo ""

# Проверка прав root
if [ "$EUID" -ne 0 ]; then 
    echo "⚠️  Запустите скрипт с правами root: sudo bash install.sh"
    exit 1
fi

# Получаем имя пользователя, который запустил sudo
REAL_USER=${SUDO_USER:-$USER}
REAL_HOME=$(eval echo ~$REAL_USER)

# Установка директории
INSTALL_DIR="$REAL_HOME/gallery_bot"

echo "📁 Директория установки: $INSTALL_DIR"
echo ""

# Обновление системы
echo "🔄 Обновление системы..."
apt-get update -qq

# Установка Python 3 и pip
echo "🐍 Установка Python 3 и pip..."
apt-get install -y python3 python3-pip python3-venv -qq

# Установка дополнительных утилит
echo "🛠️  Установка дополнительных утилит..."
apt-get install -y git curl wget nano -qq

# Создание директории для бота
echo "📂 Создание директории проекта..."
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Создание виртуального окружения
echo "🔧 Создание виртуального окружения..."
python3 -m venv venv

# Активация виртуального окружения
source venv/bin/activate

# Установка зависимостей Python
echo "📦 Установка зависимостей Python..."
pip install --upgrade pip -q
pip install python-telegram-bot python-dotenv -q

# Создание .env файла
echo "⚙️  Создание файла конфигурации..."
cat > "$INSTALL_DIR/.env" << 'EOF'
# Конфигурация Gallery Bot

# Токен бота (получите у @BotFather в Telegram)
BOT_TOKEN=your_bot_token_here

# ID администратора (ваш Telegram ID, получите у @userinfobot)
ADMIN_ID=your_admin_id_here

# Файлы данных
DATA_FILE=gallery_data.json
FILES_DIR=gallery_files
LOGS_FILE=error_logs.json
EOF

# Создание requirements.txt
cat > "$INSTALL_DIR/requirements.txt" << 'EOF'
python-telegram-bot==20.7
python-dotenv==1.0.0
EOF

# Создание systemd сервиса
echo "🔧 Создание systemd сервиса..."
cat > /etc/systemd/system/gallery-bot.service << EOF
[Unit]
Description=Gallery Telegram Bot
After=network.target

[Service]
Type=simple
User=$REAL_USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/gallery_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Создание скрипта запуска
cat > "$INSTALL_DIR/start.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
python gallery_bot.py
EOF

chmod +x "$INSTALL_DIR/start.sh"

# Создание скрипта остановки
cat > "$INSTALL_DIR/stop.sh" << 'EOF'
#!/bin/bash
sudo systemctl stop gallery-bot
echo "✅ Бот остановлен"
EOF

chmod +x "$INSTALL_DIR/stop.sh"

# Создание скрипта перезапуска
cat > "$INSTALL_DIR/restart.sh" << 'EOF'
#!/bin/bash
sudo systemctl restart gallery-bot
echo "✅ Бот перезапущен"
EOF

chmod +x "$INSTALL_DIR/restart.sh"

# Создание скрипта просмотра логов
cat > "$INSTALL_DIR/logs.sh" << 'EOF'
#!/bin/bash
sudo journalctl -u gallery-bot -f
EOF

chmod +x "$INSTALL_DIR/logs.sh"

# Создание скрипта обновления
cat > "$INSTALL_DIR/update.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
echo "🔄 Остановка бота..."
sudo systemctl stop gallery-bot

echo "📦 Обновление зависимостей..."
source venv/bin/activate
pip install --upgrade -r requirements.txt

echo "🚀 Запуск бота..."
sudo systemctl start gallery-bot

echo "✅ Обновление завершено!"
EOF

chmod +x "$INSTALL_DIR/update.sh"

# Создание README
cat > "$INSTALL_DIR/README.md" << 'EOF'
# Gallery Bot - Инструкция

## 📋 Первоначальная настройка

1. Откройте файл `.env` и укажите:
   ```bash
   nano .env
   ```
   - `BOT_TOKEN` - токен от @BotFather
   - `ADMIN_ID` - ваш Telegram ID от @userinfobot

2. Скопируйте файл `gallery_bot.py` в эту директорию

3. Запустите бота:
   ```bash
   sudo systemctl start gallery-bot
   sudo systemctl enable gallery-bot  # Автозапуск при загрузке
   ```

## 🎮 Управление ботом

### Запуск
```bash
sudo systemctl start gallery-bot
# или
./start.sh
```

### Остановка
```bash
sudo systemctl stop gallery-bot
# или
./stop.sh
```

### Перезапуск
```bash
sudo systemctl restart gallery-bot
# или
./restart.sh
```

### Просмотр логов
```bash
sudo journalctl -u gallery-bot -f
# или
./logs.sh
```

### Статус
```bash
sudo systemctl status gallery-bot
```

### Обновление зависимостей
```bash
./update.sh
```

## 📁 Структура файлов

- `gallery_bot.py` - основной файл бота
- `.env` - конфигурация (токены, ID)
- `gallery_data.json` - база данных
- `gallery_files/` - загруженные файлы
- `error_logs.json` - логи ошибок
- `venv/` - виртуальное окружение Python

## 🔧 Автозапуск

Включить автозапуск при загрузке сервера:
```bash
sudo systemctl enable gallery-bot
```

Отключить автозапуск:
```bash
sudo systemctl disable gallery-bot
```

## 📝 Логи

Просмотр последних 100 строк:
```bash
sudo journalctl -u gallery-bot -n 100
```

Просмотр логов за сегодня:
```bash
sudo journalctl -u gallery-bot --since today
```

## 🔄 Обновление бота

1. Остановите бота: `./stop.sh`
2. Замените файл `gallery_bot.py`
3. Запустите бота: `./start.sh`

## ⚠️ Важно

- Не удаляйте файлы `gallery_data.json` и папку `gallery_files/`
- Регулярно делайте резервные копии данных
- Храните `.env` в безопасности (не публикуйте токены)
EOF

# Установка правильных прав доступа
chown -R $REAL_USER:$REAL_USER "$INSTALL_DIR"

# Перезагрузка systemd
systemctl daemon-reload

echo ""
echo "=================================="
echo "  ✅ Установка завершена!"
echo "=================================="
echo ""
echo "📁 Директория: $INSTALL_DIR"
echo ""
echo "📝 Следующие шаги:"
echo ""
echo "1. Скопируйте gallery_bot.py в директорию:"
echo "   cp gallery_bot.py $INSTALL_DIR/"
echo ""
echo "2. Настройте конфигурацию:"
echo "   nano $INSTALL_DIR/.env"
echo "   (укажите BOT_TOKEN и ADMIN_ID)"
echo ""
echo "3. Запустите бота:"
echo "   sudo systemctl start gallery-bot"
echo "   sudo systemctl enable gallery-bot  # автозапуск"
echo ""
echo "4. Проверьте статус:"
echo "   sudo systemctl status gallery-bot"
echo ""
echo "📖 Полная инструкция: $INSTALL_DIR/README.md"
echo ""
