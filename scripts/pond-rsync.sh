#!/bin/bash

# fail fast on error, unset variable, or pipe failure
set -euo pipefail

echo `date` start rsync 
cd ~/projects/pond

echo rsync from `hostname` to gcweb

cp -f ./output/booking-plot-*.png ./www-root/

echo `date` start rsync gcweb1

rsync -av ./www-root/index.html gcweb1:projects/heating/dev/www-root
rsync -av ./www-root/bookings.html gcweb1:projects/heating/dev/www-root
rsync -av ./www-root/booking-plot-*.png gcweb1:projects/heating/dev/www-root

echo `date` end pond rsync


