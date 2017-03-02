<!--
  Licensed to the Apache Software Foundation (ASF) under one or more
  contributor license agreements.  See the NOTICE file distributed with
  this work for additional information regarding copyright ownership.
  The ASF licenses this file to You under the Apache License, Version 2.0
  (the "License"); you may not use this file except in compliance with
  the License.  You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.
-->
# Overview
[![Build Status](https://travis-ci.org/juju-solutions/layer-cwr.svg?branch=master)](https://travis-ci.org/juju-solutions/layer-cwr)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

This subordinate charm prepares a Jenkins master node to test Juju artifacts
(charms and bundles).


# Deployment

A working Juju installation is assumed to be present. If Juju is not yet set
up, please follow the [getting-started][] instructions prior to deploying this
charm.

This charm is intended to be deployed as part of the [cwr-ci bundle][]:

    juju deploy cs:~juju-solutions/cwr-ci

> **Note**: This bundle requires Juju 2.0 or greater.

This will deploy Jenkins with this charm acting as the charm/bundle test
mechanism. More information about this deployment can be found in the
[bundle readme][cwr-ci bundle].

## Status
This charm provides extended status to indicate when it is ready:

    juju status

This is particularly useful when combined with `watch` to track the on-going
progress of the deployment:

    watch -c juju status --color

The message column will provide information about this unit's state.

## Network-Restricted Environments
Charms can be deployed in environments with limited network access. To deploy
in this environment, configure a Juju model with appropriate proxy and/or
mirror options. See [Configuring Models][] for more information.

[getting-started]: https://jujucharms.com/docs/stable/getting-started
[cwr-ci bundle]: https://jujucharms.com/u/juju-solutions/cwr-ci
[Configuring Models]: https://jujucharms.com/docs/stable/models-config


# Configuration

This charm needs access to your controller(s) to create models and allocate
resources needed to run charm/bundle tests. The steps required to do this
are covered in detail in the *Getting Started* section of the
[cwr-ci bundle readme][cwr-ci bundle]. A summary of the procedure is as
follows:

* Add a user to your controller(s)
* Grant `add-model` permissions to the new user(s)
* Run the `register-controller` action
* Run the `set-credentials` action
* Optionally run the `store-login` action


# Usage

The test capabilities of this charm are covered in detail in the *Workflows*
section of the [cwr-ci bundle readme][cwr-ci bundle]. At a glance, the
following usage scenarios are supported via charm actions:

* Test a charm when a commit is made to a charm source repository
* Test a charm when a [release][gh-release] is created in a Github charm source
repository
* Test a charm when a pull request is created in a Github charm source
repository
* Test a bundle when an included charm is updated in the Charm Store

[gh-release]: https://help.github.com/articles/creating-releases/


# Resources

## Community

- `#juju` on Freenode
- [Juju mailing list](https://lists.ubuntu.com/mailman/listinfo/juju)
- [Juju community](https://jujucharms.com/community)

## Technical

CWR leverages a plethora of tooling from the Juju ecosystem.
Details can be found at the following project links:

- [cloud-weather-report](https://github.com/juju-solutions/cloud-weather-report)
- [bundletester](https://github.com/juju-solutions/bundletester)
- [matrix](https://github.com/juju-solutions/matrix)
- [python-libjuju](https://github.com/juju/python-libjuju)
