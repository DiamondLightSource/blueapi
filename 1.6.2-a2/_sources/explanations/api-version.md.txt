# API Version

Blueapi has [released versions](https://github.com/DiamondLightSource/blueapi/releases) that are complaint with [semantic versioning](https://semver.org/) to make updating/rolling back as easy as possible. Blueapi's [REST API](../reference/rest-spec.md) is versioned separately to the main application, since not all changes will affect it. The idea is that a change in the REST API version is a signal to client developers that they may need to do some work to update.

If you are a developer contributing a PR, there is a unit test that will fail if the REST API has changed in your PR but the version defined in the code, [](#REST_API_VERSION), has not been updated. You should update the version for _any_ change to the API at all, whether it's a major, minor or patch update is to be determined by the developer(s) and the reviewer(s) involved. _Do not_ update [`docs/reference/openapi.yaml`](../reference/openapi.yaml), it is checked against `main` in CI. 
