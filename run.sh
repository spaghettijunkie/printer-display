#!/bin/bash
export DISPLAY=:0
echo -e "\n\n\nNEW LOG: $now\n\n\n"  >> log.txt
python3 mainv3.py 2>&1 | tee -a log.txt

