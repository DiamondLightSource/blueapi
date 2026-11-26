# Changelog

## [1.23.0](https://github.com/DiamondLightSource/blueapi/compare/1.22.0...1.23.0) (2026-11-26)


### Features

* Allow keepAlive for numtracker connections ([#1790](https://github.com/DiamondLightSource/blueapi/issues/1790)) ([0117608](https://github.com/DiamondLightSource/blueapi/commit/0117608d42cb05207139503fab452566abbc5b6b))
* Register child devices as top level devices ([#1739](https://github.com/DiamondLightSource/blueapi/issues/1739)) ([5884bfd](https://github.com/DiamondLightSource/blueapi/commit/5884bfdc66184511c9ef57db229d3368cfcb5500))
* **scratch:** add uv lock file ([#1742](https://github.com/DiamondLightSource/blueapi/issues/1742)) ([04616b7](https://github.com/DiamondLightSource/blueapi/commit/04616b750fb05da5c5bec7ca5202ec51000e45c5))
* use precommit config for prek ([#1793](https://github.com/DiamondLightSource/blueapi/issues/1793)) ([af3eebb](https://github.com/DiamondLightSource/blueapi/commit/af3eebbd3a3e4e84599bee165e39d3739603c3a8))


### Bug Fixes

* Ignore missing task ID when removing from _pending ([#1735](https://github.com/DiamondLightSource/blueapi/issues/1735)) ([065ce78](https://github.com/DiamondLightSource/blueapi/commit/065ce7858cf016742d115e630f71d866942eae30))
* Move docs redirect to the open_router ([#1756](https://github.com/DiamondLightSource/blueapi/issues/1756)) ([9a86cd2](https://github.com/DiamondLightSource/blueapi/commit/9a86cd2407c17e1b763283d0a9c23249b4382d5b))
* move PR template to correct place ([#1792](https://github.com/DiamondLightSource/blueapi/issues/1792)) ([362059a](https://github.com/DiamondLightSource/blueapi/commit/362059a2996e789e5ecf1c4ee29d72c038354a9c))


### Documentation

* Add an LLM/genAI policy to CONTRIBUTING.md ([#1777](https://github.com/DiamondLightSource/blueapi/issues/1777)) ([49d96a9](https://github.com/DiamondLightSource/blueapi/commit/49d96a970435928bc90a12d1383b4596a1edba3d))
* Reformat CONTRIBUTING.md ([#1780](https://github.com/DiamondLightSource/blueapi/issues/1780)) ([5a9e840](https://github.com/DiamondLightSource/blueapi/commit/5a9e840e2befc081c8a57f11e25c123a305ac52e))
* Update contribution guidelines ([#1767](https://github.com/DiamondLightSource/blueapi/issues/1767)) ([89fda25](https://github.com/DiamondLightSource/blueapi/commit/89fda25f05cff3786a70b87c353f43b2cffe171d))


### Code Refactoring

* Combine plans and plan_functions  ([#1743](https://github.com/DiamondLightSource/blueapi/issues/1743)) ([f0c530c](https://github.com/DiamondLightSource/blueapi/commit/f0c530cef88f1b47895998f3dfe09e0ccacd730d))
* Extract constant for config path in justfile ([#1751](https://github.com/DiamondLightSource/blueapi/issues/1751)) ([4701980](https://github.com/DiamondLightSource/blueapi/commit/4701980c973650b546b6d68dcfad2d9c668b6924))
* make client almost client again ([#1666](https://github.com/DiamondLightSource/blueapi/issues/1666)) ([7cf9bd8](https://github.com/DiamondLightSource/blueapi/commit/7cf9bd8a7e8e4255e8e50c6466018481721d44b7))
* remove correlation dead code ([#1763](https://github.com/DiamondLightSource/blueapi/issues/1763)) ([01acea3](https://github.com/DiamondLightSource/blueapi/commit/01acea32ba0625e6af3ee577fdd69c78b849a198)), closes [#661](https://github.com/DiamondLightSource/blueapi/issues/661)
* replace tomlkit with stdlib tomllib ([#1664](https://github.com/DiamondLightSource/blueapi/issues/1664)) ([1908cff](https://github.com/DiamondLightSource/blueapi/commit/1908cff27e78d644c6498360eeeaec70e0ec7ba2)), closes [#1746](https://github.com/DiamondLightSource/blueapi/issues/1746)
* Wrap Devices in BlueapiDevice ([#1744](https://github.com/DiamondLightSource/blueapi/issues/1744)) ([a4ce435](https://github.com/DiamondLightSource/blueapi/commit/a4ce435d4e4db241978e30657a8d5627258584d4))


### CI

* Add CodeRabbit configuration ([#1811](https://github.com/DiamondLightSource/blueapi/issues/1811)) ([fe8c82d](https://github.com/DiamondLightSource/blueapi/commit/fe8c82d1dc5bbc589ae25d58890e899c00c83b06))
* add dx commit type ([#1794](https://github.com/DiamondLightSource/blueapi/issues/1794)) ([b92b3e0](https://github.com/DiamondLightSource/blueapi/commit/b92b3e00c4a7c8f9f1db254b0ba1a04ea03f7f2b))
* Add release please ([#1765](https://github.com/DiamondLightSource/blueapi/issues/1765)) ([7ce6935](https://github.com/DiamondLightSource/blueapi/commit/7ce693524b8ebfa2306202e0765ca77686e02e79))
* Update ruff version used in prek ([#1778](https://github.com/DiamondLightSource/blueapi/issues/1778)) ([41a3d57](https://github.com/DiamondLightSource/blueapi/commit/41a3d57303b944981ff3349fc883dc6b7fd16c8a))


### Miscellaneous

* Add 'listen' task to justfile ([#1750](https://github.com/DiamondLightSource/blueapi/issues/1750)) ([b8c1dc0](https://github.com/DiamondLightSource/blueapi/commit/b8c1dc00b8a76eb5ce0e5c95390249f88819dae6))
* **deps:** Remove support for python 3.11 and 3.12 ([#1787](https://github.com/DiamondLightSource/blueapi/issues/1787)) ([c2f6911](https://github.com/DiamondLightSource/blueapi/commit/c2f6911f2e74150332bb7f35036d2aec7cd6d67b))
* **deps:** update actions/create-github-app-token action to v3.4.0 ([#1798](https://github.com/DiamondLightSource/blueapi/issues/1798)) ([d6ae5b0](https://github.com/DiamondLightSource/blueapi/commit/d6ae5b0e1818e1984089d43baa20d92c8f8d22f3))
* **deps:** update asyncapi/cli action to v6.3.1 ([#1745](https://github.com/DiamondLightSource/blueapi/issues/1745)) ([5424f13](https://github.com/DiamondLightSource/blueapi/commit/5424f13ef59f1770ac803ed3ca5fb2b41a34c5b3))
* **deps:** update azure/setup-helm digest to 2f5e7bc ([#1747](https://github.com/DiamondLightSource/blueapi/issues/1747)) ([4bb49a9](https://github.com/DiamondLightSource/blueapi/commit/4bb49a930f4907391ba7f71a2c05138ce3a0ce1e))
* **deps:** update dependency dnspython to v2.9.2 [security] ([#1761](https://github.com/DiamondLightSource/blueapi/issues/1761)) ([59f8fea](https://github.com/DiamondLightSource/blueapi/commit/59f8fea0f4af5ad2365bf5e851c32b693485ad58))
* **deps:** update dependency opentelemetry-api to v1.45.2 [security] ([#1762](https://github.com/DiamondLightSource/blueapi/issues/1762)) ([6ad2c10](https://github.com/DiamondLightSource/blueapi/commit/6ad2c1040067e982179ceb5c94593d9a37d1e411))
* **deps:** update pre-commit hook astral-sh/ruff-pre-commit to v0.17.6 ([#1799](https://github.com/DiamondLightSource/blueapi/issues/1799)) ([74b512f](https://github.com/DiamondLightSource/blueapi/commit/74b512fc5a96e6b4f9bfc47c43f81213e735ec0c))
* **deps:** update pre-commit hook astral-sh/uv-pre-commit to v0.13.10 ([#1813](https://github.com/DiamondLightSource/blueapi/issues/1813)) ([ddbd694](https://github.com/DiamondLightSource/blueapi/commit/ddbd694714ddf4523fc8079caa7d27402bfa1d21))
* **deps:** update pre-commit hook astral-sh/uv-pre-commit to v0.13.9 ([#1800](https://github.com/DiamondLightSource/blueapi/issues/1800)) ([482279d](https://github.com/DiamondLightSource/blueapi/commit/482279ddb55e19fd8a53402d786dcba82299e3ea))
* fix typos ([#1789](https://github.com/DiamondLightSource/blueapi/issues/1789)) ([02eb95b](https://github.com/DiamondLightSource/blueapi/commit/02eb95beac9773cf4e0a42f1e2f2c9a110feeb25))
* Increase the default ephemeral storage request ([#1759](https://github.com/DiamondLightSource/blueapi/issues/1759)) ([71de222](https://github.com/DiamondLightSource/blueapi/commit/71de222d422fafd8b84044a798886d300138c6a6)), closes [#1626](https://github.com/DiamondLightSource/blueapi/issues/1626)
* Nexus for diamond testing ([#1758](https://github.com/DiamondLightSource/blueapi/issues/1758)) ([1e761f9](https://github.com/DiamondLightSource/blueapi/commit/1e761f9080170c7975940be13c3d0eb7033a8783))
* Update client to use versioned API ([#1512](https://github.com/DiamondLightSource/blueapi/issues/1512)) ([fe7601f](https://github.com/DiamondLightSource/blueapi/commit/fe7601fbdc80ca88190d984f1573cfab053e12b5))
