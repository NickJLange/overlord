#!/bin/bash

cd ../ansible/

declare -x DIRECTION=$1

#kids
for i in kids_bedroom entrance master_bedroom office_overhead_1;
 do declare -x ROOM=$i
    ansible-playbook -i inventory -e 'hostlist='$ROOM  -e "Power=Power" -e 'State='$DIRECTION tasmota_command.yml
    sleep $[($RANDOM % 30 + 1)]
done
