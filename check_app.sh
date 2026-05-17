#!/bin/bash
APP_DIR="/home3/amitawn2/sports-league/backend"
cd $APP_DIR

if ! pgrep -f "python3 run.py" > /dev/null; then
    echo "App crashed. Restarting..."
    nohup python3 run.py > app.log 2>&1 &
fi
