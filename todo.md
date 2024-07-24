
# todos

## done
- [x] all handler references should be replaced by the grpc client OR just the refernce to the context


## doable now (?)

- [ ] fix errors
- [ ] move some blueworker config types to proto
- [ ] make the new context private https://github.com/DiamondLightSource/blueapi/pull/174/files

## still awaited

- [ ] get the scratch area and then decide blueapi and blueworker config
- [ ] the api can pass the path or they each do independent discovery of the shared volume


## deployment

Since they communicate via gRPC, they are already decoupled at a functional level, making them good candidates for separate deployment.
https://packaging.python.org/en/latest/guides/packaging-namespace-packages/
this is a thing, with the highermost 'services' as just a namespace.


- [ ] can deploy one package just with different entrypoints
- [ ] move the initalization logic away from CLI
- [ ] even the same dockerfile, just different entrypoints

