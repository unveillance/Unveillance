#! /bin/bash

sudo service ssh start
sudo cron -f &
tail -f /dev/null