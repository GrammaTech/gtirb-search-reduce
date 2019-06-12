#!/bin/bash

docker run -it \
       --mount type=bind,source="$(pwd)",target=/development \
       --ulimit core=0 \
       -w=/development \
       search-debloater
