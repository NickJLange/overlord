#!/bin/bash


declare -x BASEURL=http://terrabeta:8082/

declare -x DIRECTION=$1

if [ -z $DIRECTION ];
  then echo "missing direction [on|off]";
  exit 1
 fi

if [ "$DIRECTION" == "on" ]; then
  declare -x METHOD=POST
elif [ "$DIRECTION" == "off" ]; then
  declare -x METHOD=DELETE
else
  declare -x METHOD=GET
fi

#kids
for i in dplus netflix hbomax youtube playstation; do
  curl -q -X $METHOD $BASEURL/$i
done