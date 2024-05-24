#!/usr/bin/env bash

# Set umask to DLS standard
umask 0002

if [[ -z "${SCRATCH_AREA}" ]]; then
  SCRATCH_AREA="/blueapi-plugins/scratch"
fi

if [[ -d "${SCRATCH_AREA}" ]]; then
  echo "Loading Python packages from ${SCRATCH_AREA}"
  for DIR in ${SCRATCH_AREA}/*/; do # All directories
    python -m pip install --no-deps -e "${DIR}"
  done
else
  echo "blueapi scratch area not present"
fi

blueapi $@
