#!/bin/sh

set -e 

if test -d audio ; then cd audio
elif test -d ../audio ; then cd ../audio
else echo "No audio subdir"; exit 1; fi

make

./writer rate 32000 fs20 exec cat < ../test/expect/fs20rw | ./reader rate 32000 fs20 exec cat > ../test/real/fs20rw

