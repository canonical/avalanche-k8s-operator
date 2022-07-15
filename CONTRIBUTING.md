# Contributing to avalanche-operator
![GitHub](https://img.shields.io/github/license/canonical/avalanche-k8s-operator) ![GitHub commit activity](https://img.shields.io/github/commit-activity/y/canonical/avalanche-k8s-operator) ![GitHub](https://img.shields.io/tokei/lines/github/canonical/avalanche-k8s-operator)
![GitHub](https://img.shields.io/github/issues/canonical/avalanche-k8s-operator) ![GitHub](https://img.shields.io/github/issues-pr/canonical/avalanche-k8s-operator) ![GitHub](https://img.shields.io/github/contributors/canonical/avalanche-k8s-operator) ![GitHub](https://img.shields.io/github/watchers/canonical/avalanche-k8s-operator?style=social)

The intended use case of this operator is to be deployed together with
prometheus-operator.

## Bugs and pull requests
- Generally, before developing enhancements to this charm, you should consider
  opening an issue explaining your use case.
- If you would like to chat with us about your use-cases or proposed
  implementation, you can reach us at
  [Canonical Mattermost public channel](https://chat.charmhub.io/charmhub/channels/charm-dev)
  or [Discourse](https://discourse.charmhub.io/).
- All enhancements require review before being merged. Apart from
  code quality and test coverage, the review will also take into
  account the resulting user experience for Juju administrators using
  this charm.


## Setup

A typical setup using [snaps](https://snapcraft.io/) can be found in the
[Juju docs](https://juju.is/docs/sdk/dev-setup).

## Developing

Use your existing Python 3 development environment or create and
activate a Python 3 virtualenv

```shell
virtualenv -p python3 venv
source venv/bin/activate
```

Install the development requirements

```shell
pip install -r requirements.txt
```

Later on, upgrade packages as needed

```shell
pip install --upgrade -r requirements.txt
```

### Testing

```shell
tox -e fmt    # update your code according to linting rules
tox -e lint   # code style
tox -e static # static analysis
tox -e unit   # unit tests
```

tox creates virtual environment for every tox environment defined in
[tox.ini](tox.ini). To activate a tox environment for manual testing,

```shell
source .tox/unit/bin/activate
```

## Build charm

Build the charm in this git repository using

```shell
charmcraft pack
```

## Usage
### Tested images
- [quay.io/freshtracks.io/avalanche](https://quay.io/freshtracks.io/avalanche)

### Deploy Avalanche

```shell
juju deploy ./avalanche-k8s_ubuntu-20.04-amd64.charm \
  --resource avalanche-image=quay.io/freshtracks.io/avalanche
```

## Code overview
- The main charm class is `AvalancheCharm`, which responds to config changes
  (via `ConfigChangedEvent`) and application upgrades (via
  `UpgradeCharmEvent`).
- All lifecycle events call a common hook, `_common_exit_hook` after executing
  their own business logic. This pattern simplifies state tracking and improves
  consistency.

## Design choices
NTA

## Roadmap
TBD
