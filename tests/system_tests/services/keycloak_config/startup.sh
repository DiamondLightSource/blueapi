#!/bin/bash
export PATH=$PATH:/opt/keycloak/bin

sleep 30
while ! kcadm.sh config credentials --server http://localhost:8080 --realm master --user admin --password admin; do
    sleep 1
done

# Add users to Keycloak
for user in alice bob carol; do
  kcadm.sh create users -r master -s username="$user" -s enabled=true
  kcadm.sh set-password -r master --username "$user" --new-password "$user"
done

allowed_protocol_mappers=$(kcadm.sh get components -q name="Allowed Protocol Mapper Types" --fields id --format csv --noquotes)
allowed_client_scopes=$(kcadm.sh get components -q name="Allowed Client Scopes" --fields id --format csv --noquotes)
for i in $allowed_protocol_mappers $allowed_client_scopes;do
  kcadm.sh delete components/$i
done

kcreg.sh config credentials --server http://localhost:8080 --realm master --user admin --password admin
kcreg.sh get "blueapi-ci" >/dev/null 2>&1 || kcreg.sh create --file "/mnt/blueapi-ci.json"
