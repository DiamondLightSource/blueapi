podman run --rm \
  -v ${PWD}:/local openapitools/openapi-generator-cli generate \
  -i /local/docs/reference/schema-for-autogen.yaml \
  -g python-pydantic-v1 \
  -o /local/src/clients/python
