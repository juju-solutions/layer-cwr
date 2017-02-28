# Overview
[![Build Status](https://travis-ci.org/juju-solutions/layer-cwr.svg?branch=master)](https://travis-ci.org/juju-solutions/layer-cwr)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

This subordinate charm prepares a Jenkins master node to test Juju artifacts
(charms and bundles).


# Configuration

This charm needs access to your controller(s) to create models and allocate
resources needed to run charm/bundle tests. Grant this by creating a user on
your bootstrapped controller(s) with appropriate permissions:

    juju add-user ciuser
    juju grant ciuser add-model

Now register your controller with CWR by calling the `register-controller`
action. Provide the controller name and the registration token from the above
`juju add-user` command:

    juju run-action cwr/0 register-controller name=<controller-name> \
        token=<registration-token>

If you're using a cloud that requires credentials (i.e., anything other than
the LXD provider), you will need to provide those credentials as base64-encoded
YAML. You can find your credentials in `~/.local/share/juju/credentials.yaml`,
but you may want to extract and share just the portions that will be
used with the CI system.  In the future, Juju should provide a way to
share access to the credentials without having to share the credentials
themselves. Until then, inform CWR of your controller credentials with the
`set-credentials` action:

    juju run-action cwr/0 set-credentials cloud=<cloud-name> \
        credentials="$(base64 credentials.yaml)"

Finally, you may setup a session with the charm store that allows CWR to
release charms to your namespace. To do this, call the `store-login` action
and provide the base64 representation of an existing auth token:

    charm login
    .........
    juju run-action cwr/0 store-login \
        charmstore-usso-token="$(base64 ~/.local/share/juju/store-usso-token)"

The charm store session will remain active while the CI system is online. To
terminate the session, run the `store-logout` action:

    juju run-action cwr/0 store-logout

Note that these actions are also available as jobs in Jenkins and can be run
from the Jenkins workspace if desired.


# Workflows

CWR actions assist in wiring your github repository with the CI system in a
variety of ways.

## CWR on Charm Source Commit

If you want CWR to build your charm, test it and (optionally) release it to
the charm store, call the `cwr-charm-commit` action. This action takes the
following parameters:
  - repo: The github repo of the charm or top layer
  - charm-name: The name of the charm to test
  - reference-bundle: Charm store URL of a bundle to use to test the
    given charm (e.g.: `cs:bundle/mediawiki-single`).
    If this is not provided, the charm must set it in its tests.yaml.
  - controller (optional): Name of the controller to use for running the tests.
    If you do not specify a controller tests will run on all registered
    controllers.
  - repo-access (optional): 'webhook' or 'poll'. By default the action
    will produce a URL to be used as a webhook that will trigger the build.
    Alternatively you can set repo-access to 'poll' to periodically
    (once every 5 minutes) to poll the repository for changes.
    See details below.

Should you decide to release a charm after a successful test, you can also
specify:
  - push-to-channel: Channel to be used (e.g.: edge, beta, candidate, stable)
  - namespace: The namespace (typically a launchpad id) you want the charm
    released under (e.g.: `awesome-team`)

An example run of this action might look like this:

    juju run-action cwr/0 cwr-charm-commit \
      repo=https://github.com/juju-solutions/layer-cwr \
      charm-name=cwr \
      reference-bundle=cs:~juju-solutions/cwr-ci \
      push-to-channel=edge \
      namespace=juju-solutions \
      controller=lxd

Running this action will result in a new job in Jenkins called
`cwr-charm-commit-{charm-name}-in-{reference-bundle}`. You can have the job
triggered externally through a web hook or you can set periodic polling of
your repository via the "repo-access" action parameter:

  - webhook: the action will output a web hook that you can use
    to trigger the build of your repository. You can get the output of the
    action with:

        juju show-action-output <action_id>

    Should the action succeed, the webhook url produced will have the following
    format:

        http://<jenkins_machine>:5000/ci/v1.0/trigger/<job>/<uuid>

    You will need to add this webhook under Settings->Webhooks
    of your github repository.

  - poll: when setting "repo-access" to 'poll' the jenkins job produced by
    the action will poll your github repository for changes.
    Note that in this repo-access mode this charm will immediately trigger the
    an initial execution the jenkins jobs. This is required so that successive
    polls will correctly compute the source code delta from the previous poll.


## CWR on Charm Source Release

If you want to drive your releases using tags directly from github, call the
`cwr-charm-release` action. This action has the same set of parameters as
`cwr-charm-commit`, but the resulting job will build/test/push your charm only
when you add a release tag to your github repository. Note that calling this
action with "repo-access" set to 'poll' will result in as many initial jenkins
job executions as the number of release tags present in your repository.

Running this action will result in a new job in Jenkins called
`cwr-charm-release-{charm-name}-in-{reference-bundle}`. You can have the job
triggered externally through a web hook or you can set periodic polling of
your repository via the "repo-access" parameter described above.


## CWR on Charm Source Pull Requests

To automatically CI any pull requests submitted against a repository, use the
`cwr-charm-pr` action. This action has the same set of parameters as
`cwr-charm-commit`, but the resulting job will build/test/push your charm only
if you add a release tag to your github repository.

If you also want CWR CI to comment on the PR with the out come of the tests,
you must provide an OAuth token with proper permission. Please follow the instructions
[here](https://help.github.com/articles/creating-an-access-token-for-command-line-use/)
to produce a token. The action parameter used to set the OAuth token is:
  - oauth-token (optional): OAuth token to use to comment on the PR.

An example run of this action might look like this:

    juju run-action cwr/0 cwr-charm-pr \
      repo=https://github.com/juju-solutions/layer-cwr \
      charm-name=cwr \
      reference-bundle=cs:~juju-solutions/cwr-ci \
      push-to-channel=edge \
      namespace=juju-solutions \
      controller=lxd \
      oauth-token=1234567890

Running this action will result in a new job in Jenkins called
`cwr-charm-pr-{charm-name}-in-{reference-bundle}`. This job is triggered
directly from GitHub with a web hook. Should the action succeed, the webhook
url produced will have the following format:

        http://<jenkins_machine>:5000/ci/v1.0/pr-trigger/<job>/<uuid>

You will need to add this webhook under Settings->Webhooks of your github
repository.


## CWR Bundles

With the `cwr-bundle` action, you are able to CI your bundles using the
charms released in specific channels of the charm store. This action takes the
following parameters:
  - repo: The github repo of the bundle
  - branch (optional): The branch of the github repo where the bundle is.
  - branch (optional): The branch of the github repo where the bundle is.
  - bundle-subdir (optional): The subdirectory in the repo where the
                              bundle is located.
  - bundle-name: The name of the bundle
  - controller: Name of the controller to use for running the tests

This action will create a Jenkins job that will grab
the repository with your bundle, read the bundle.yaml and see if there are
any charms that can be updated. If an update is possible,
the bundle.yaml will be updated and all tests of the bundle will run.
If the tests are successful this job could also release the bundle
and the charms to the store.
The job will run periodically (every 10 minutes), but you can also trigger the job
via a webhook. The webhoock URL is shown in the action's output
and would require you to perform a POST request with at least an empty payload
(compatible to the [GitHub Push Event Webhook](https://developer.github.com/v3/activity/events/types/#pushevent)).

The `cwr-bundle` action requires you to have a `ci-info.yaml` file in your
bundle repository. An example yaml should look like:

```
bundle:
  name: cwr-ci
  namespace: juju-solutions
  release: true
  to-channel: beta
charm-upgrade:
  cwr:
    from-channel: edge
    release: true
    to-channel: beta
```

Under bundle you should set the bundle `name`.
Should you decide to also release the bundle upon a successful update and test cycle
you should set the `release` to true, the `namespace` to where you want to release
the bundle to (`cs:~<namespace>/<name>`) and the channel you want the bundle released
to.

In the `charm-upgrade` you can have the list of charms you want to be upgraded.
Note that you can choose to upgrade only a subset of charms. Furthermore,
for each charm you can specify the channel in which the CI should look for new revisions
and (optionally) channel the charm should be released to in case of a successful
test.

An example run of this action might look like this:

    juju run-action cwr/0 cwr-bundle \
      repo=https://github.com/juju-solutions/bundle-cwr-ci \
      branch=master  \
      bundle-name=cwr-ci \
      controller=lxd


The above actions give you a basic yet powerful CI workflow for charms and
bundles.


# Build Badge

The CI offers an SVG badge showing the current build status. An example use of
this badge would be for reporting CI status in README files. Each jenkins job
has its own build badge URL shown as part of the action output used to set up
the job. To view the badge URL, run:

    juju show-action-output <action-id>

with the action id of any of a `cwr-bundle`, `cwr-charm-commit`, or
`cwr-charm-release` action.

The badge URL is of the following form:

    http://<Jenkins_machine>:5000/<jenkins_job_name>/build-badge.svg

You will need to make sure the CI is reachable from the location where the badge is
shown, so make sure you have exposed the cwr service.

Given your README is using a markup language, using the badge should be as easy as:

    [![Build Status](http://<Jenkins_machine>:5000/<jenkins_job_name>/build-badge.svg)](http://<Jenkins_machine>:5000/)

A build badge will report the test result of Cloud Weather Report for all clouds
on which the job was run. An example looks like this:

![alt text](https://camo.githubusercontent.com/ebf2531c70134716f3778449305fdf3b3a4be015/68747470733a2f2f63646e2e7261776769742e636f6d2f6a6f686e7363612f62366639623364313230313937363132656135313639666664343531663635352f7261772f353966613633656132386336636664656361313366326161383734303666653930363730653163392f6275696c642d62616467652e737667)

Green indicates tests passed on a particular cloud; red indicates failing tests;
yellow/orange indicates an infrastructure error (e.g., deployment failure).

# Resources

- [Juju mailing list](https://lists.ubuntu.com/mailman/listinfo/juju)
- [Juju community](https://jujucharms.com/community)
- [Jenkins](https://jenkins.io/)
