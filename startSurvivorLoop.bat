@Echo off
chcp 65001

:Start
python survivor.py
timeout 3
goto Start
