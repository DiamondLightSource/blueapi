#!/bin/sh
# Get PVCs belonging to this blueapi release
ALL_PVC=$(kubectl get pvc -n  $RELEASE_NAMESPACE  \
  -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | \
  grep "^$RELEASE_NAME-scratch-")
# Get all PVCs currently mounted by running pods
MOUNTED_PVCS=$(kubectl get pods -n  $RELEASE_NAMESPACE  \
  -o=jsonpath='{.items[*].spec.volumes[*].persistentVolumeClaim.claimName}' | tr ' ' '\n' | sort -u)
NOW=$(date +%s)
#loop through all the pvcs annotating ones thare are mounted or lack a last-used stamp
for pvc in $ALL_PVC; do
  # Checks if Annotation for last-used is empty
  ANNOTATION=$(kubectl get pvc "$pvc" -n  $RELEASE_NAMESPACE  -o=jsonpath='{.metadata.annotations.last-used}')
  # -z checks if ANNOTATION is empty, if its empty or mounted to updates last-used else it ignores it
  if [ -z "$ANNOTATION" ]; then 
    kubectl annotate --overwrite pvc "$pvc" -n  $RELEASE_NAMESPACE  last-used="$NOW"
  elif echo "$MOUNTED_PVCS" | grep -qx "$pvc"; then
    kubectl annotate --overwrite pvc "$pvc" -n  $RELEASE_NAMESPACE  last-used="$NOW"
  fi
done
