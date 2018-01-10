#!/bin/sh
# build the program!
# note: there will eventually be a separate build step for your bot, but for now it counts against your runtime.

if [[ "$OSTYPE" == "darwin"* ]]; then
	# On OS X the resolv library needs to be used instead of librt.
	# Also gcc_s seems to cause errors, but removing it works!
	LIBRARIES="-lutil -ldl -lresolv -lpthread -lc -lm -L. -lbattlecode"
else
	# Assume some Linux-y OS
	LIBRARIES="-lutil -ldl -lrt -lpthread -lgcc_s -lc -lm -L. -lbattlecode"
fi

INCLUDES="-I."
gcc main.c -o main $LIBRARIES $INCLUDES

# run the program!
./main
