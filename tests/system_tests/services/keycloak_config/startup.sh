#!/bin/bash
export PATH=$PATH:/opt/keycloak/bin

sleep 30
while ! kcadm.sh config credentials --server http://localhost:8080 --realm master --user admin --password admin; do
    sleep 1
done

allowed_protocol_mappers=$(kcadm.sh get components -q name="Allowed Protocol Mapper Types" --fields id --format csv --noquotes)
allowed_client_scopes=$(kcadm.sh get components -q name="Allowed Client Scopes" --fields id --format csv --noquotes)
for i in $allowed_protocol_mappers $allowed_client_scopes;do
  kcadm.sh delete components/$i
done

kcreg.sh config credentials --server http://localhost:8080 --realm master --user admin --password admin

for client in "ixx-blueapi" "ixx-cli-blueapi"; do
  kcreg.sh get $client >/dev/null 2>&1 || kcreg.sh create --file "/mnt/$client.json"
done
