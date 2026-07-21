#!/bin/bash

# fail fast on error, unset variable, or pipe failure
set -euo pipefail

echo `date` start rsync data
cd ~/projects/pond

echo rsync from jwpc12 to `hostname`

rsync -av jwpc12:projects/pond/data .
rsync -av jwpc12:projects/pond/metoffice-data .

echo `date` end pond data rsync


