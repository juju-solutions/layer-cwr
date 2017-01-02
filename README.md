# Overview

This subordinate charm prepares a Jenkins master node to test Juju artifacts
(charms and bundles).


# Configuration

This charm needs access to your controller(s) to create models and allocate
resources needed to run charm/bundle tests. Grant this by creating a user on
your bootstrapped controller(s) with appropriate permissions:

    juju add-user ciuser
    juju grant ciuser add-model

Now call the `register-controller` action and provide a human-friendly name and
the registration token from the above `juju add-user` command.

    juju run-action cwr/0 register-controller name=<controller-name> \
        token=<registration-token>

If you're using a cloud that requires credentials (i.e., anything other than
the LXD provider), you will also need to provide those credentials as well,
as base64-encoded YAML:

    juju run-action cwr/0 set-credentials cloud=<cloud-name> \
        credentials="$(base64 credentials.yaml)"

You can find your credentials in `~/.local/share/juju/credentials.yaml`,
but you may want to extract and share just the portions that will be
used with the CI system.  In the future, Juju should provide a way to
share access to the credentials without having to share the credentials
themselves.

To push and release build artifacts to the Juju store directly from the CI,
you will need to initialize the session between this charm and the store. To do
so, either call the `store-login` action or trigger the `InitJujuStoreSession`
jenkins job.

The `store-login` action requires a base64 representation of an existing auth
token. For example:

    charm login
    .........
    export TOKEN=`base64 ~/.local/share/juju/store-usso-token`
    juju run-action cwr/0 store-login charmstore-usso-token="$TOKEN"

The charm store session will remain active while the CI system is online. To
terminate the session, either run the `store-logout` action.

Note that these actions are also available as jobs in Jenkins and can be run
from there instead.


# Using CWR to build your Charms

We provide two actions that assist in wiring your github repository with the CI.

## Build On Commit

If you want CWR to build your charm, test it and (optionally) release it to
the charm store, call the `build-on-commit` action. This action takes the
following parameters:
  - repo: The github repo of the charm or top layer
  - charm-name: The name of the charm
  - reference-bundle: Optional charm store URL of a bundle to use to test the
    given charm (e.g.: `cs:bundle/mediawiki-single`).
  - controller: Name of the controller to use for running the tests

Should you decide to release a charm after a successful test, you can also
specify:
  - push-to-channel: Channel to be used (e.g.: edge, beta, candidate, stable)
  - lp-id: The launchpad ID/namespace you want the charm released under
    (e.g.: `cs:~bigdata-dev/mycharm`)

An example run of this action might look like this:

    juju run-action cwr/0 build-on-commit \
      repo=https://github.com/sastix/tomee-charm-layer \
      charm-name=apache-tomee  \
      push-to-channel=edge \
      lp-id=kos.tsakalozos \
      controller=lxd

Running this action will result in a new job in Jenkins called
`charm-<charmname>` that will poll the repository once every 5 minutes. In case
new commits are found, bundletester will test your charm and the result will be
pushed to the store (again, given you have opted in).

## Build on Release

If you want to drive your releases using tags directly from github, call the
`build-on-release` juju action. This job has the same set of parameters as
above but the ending jenkins job will build/test/push your charm only if you
add a tag to your github repository.

Combining the two jobs gives you a basic yet powerful CI workflow.


# Resources

- [Juju mailing list](https://lists.ubuntu.com/mailman/listinfo/juju)
- [Juju community](https://jujucharms.com/community)
- [Jenkins](https://jenkins.io/)
