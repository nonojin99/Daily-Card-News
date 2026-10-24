set -e
cd /tmp/bl
OUTD=/tmp/bl/v3
rm -rf $OUTD; mkdir -p $OUTD
./blender-4.2.3-linux-x64/blender -b -P office3.py -- $OUTD/bg.png 100 64 bg > $OUTD/bg.log 2>&1
./blender-4.2.3-linux-x64/blender -b -P office3.py -- $OUTD 100 48 layers > $OUTD/layers.log 2>&1
/tmp/venv/bin/python clean_layers.py $OUTD 81
echo ALLDONE
