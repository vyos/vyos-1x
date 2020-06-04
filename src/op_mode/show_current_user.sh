#! /bin/bash

echo -n "login     : " ; who -m

if [ -n "$VYATTA_USER_LEVEL_DIR" ]
then
    echo -n "level     : "
    basename $VYATTA_USER_LEVEL_DIR
fi

echo -n "user      : " ; id -un
echo -n "groups    : " ; id -Gn

if id -Z >/dev/null 2>&1
then
    echo -n "context   : "
    id -Z
fi
