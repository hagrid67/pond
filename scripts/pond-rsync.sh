#!/bin/bash


echo `date` start rsync 
cd ~/projects/pond

echo rsync pc19 - gcweb

echo `date` start rsync gcweb1
# this copies 10 days of files to gcweb1
rsync -av ./www-root/bookings.html gcweb1:projects/heating/dev/www-root

echo `date` end pond rsync


