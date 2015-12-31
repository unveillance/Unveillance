#! /bin/bash

THIS_DIR=`pwd`
git submodule update --init --recursive

cd $THIS_DIR/lib/Annex
./setup.sh ~/unveillance.secrets.json
source ~/.bash_profile
./update.sh all

cd $THIS_DIR/lib/Annex
chmod 0400 conf/*
python unveillance_annex.py -firstuse
