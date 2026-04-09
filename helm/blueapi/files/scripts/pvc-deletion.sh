#!/bin/sh
# Get all PVCs by running pods
ALL_PVCS=$(kubectl get pvc -n  $RELEASE_NAMESPACE  -o=jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | sort -u)
BLUEAPI_PVCS=$( echo $ALL_PVCS | tr ' ' '\n' | grep blueapi-scratch)
NOW=$(date +%s)
#loop through all pvcs.
for pvc in $BLUEAPI_PVCS; do
    #check if pvc has last-used annotation 
    if kubectl get pvc $pvc -n  $RELEASE_NAMESPACE  -o=jsonpath='{.metadata.annotations.last-used}'
    then
        #get last used annotation 
        LAST_USED=$(kubectl get pvc $pvc -n  $RELEASE_NAMESPACE  -o=jsonpath='{.metadata.annotations.last-used}')
        #checking if its not null
        if [ -n "$LAST_USED"  ]; then
            #check if last_used is older than 3 months
            if [ $(($NOW - LAST_USED)) -gt 7884000 ]; then
                #checking if the pvc is protected, if it is protected skip deletion
                if  [ "$(kubectl get pvc $pvc -n  $RELEASE_NAMESPACE  -o=jsonpath='{.metadata.annotations.protected}')" = "true" ]; then
                    echo "PVC $pvc is protected, skipping deletion"
                    continue
                fi
                #PVC has not been used for more than three months, delete it
                kubectl delete pvc "$pvc" -n  $RELEASE_NAMESPACE
            fi
        fi
    else
         echo "PVC $pvc does not have last-used annotation, skipping deletion"
    fi
done
