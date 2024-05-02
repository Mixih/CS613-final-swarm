#!/bin/bash

git clone https://github.com/noxrepo/pox pox-sources

pushd pox-sources
    git checkout gar-experimental
    cp -r pox ../
popd

rm -rf pox-sources
