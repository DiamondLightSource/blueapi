#!/usr/bin/env bash

if [[ -z "${SCRATCH_AREA}" ]]; then
  SCRATCH_AREA="/blueapi-plugins/scratch"
fi

mkdir -p ${SCRATCH_AREA}

DIRS=`ls -1 ${SCRATCH_AREA}`

echo "Loading Python packages from from ${DIRS}"

for DIR in ${DIRS}
do
    python -m pip install --no-deps -e "${SCRATCH_AREA}/${DIR}"
done

blueapi $@
