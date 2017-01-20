# Overview

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


# Using CWR to build your Charms

We provide two actions that assist in wiring your github repository with the CI.

## Build On Commit

If you want CWR to build your charm, test it and (optionally) release it to
the charm store, call the `build-on-commit` action. This action takes the
following parameters:
  - repo: The github repo of the charm or top layer
  - charm-name: The name of the charm to test
  - reference-bundle: Charm store URL of a bundle to use to test the
    given charm (e.g.: `cs:bundle/mediawiki-single`).
    If this is not provided, the charm must set it in its tests.yaml.
  - controller: Name of the controller to use for running the tests

Should you decide to release a charm after a successful test, you can also
specify:
  - push-to-channel: Channel to be used (e.g.: edge, beta, candidate, stable)
  - lp-id: The launchpad ID/namespace you want the charm released under
    (e.g.: `cs:~bigdata-dev/mycharm`)

An example run of this action might look like this:

    juju run-action cwr/0 build-on-commit \
      repo=https://github.com/juju-solutions/layer-cwr \
      charm-name=cwr \
      reference-bundle=cs:~juju-solutions/cwr-ci \
      push-to-channel=edge \
      lp-id=juju-solutions \
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


# Using CWR to CI your Bundles

## Build Bundle action

With the `build-bundle` action you are able to update your bundles using the
charms already released on the channels of the Juju store.
`build-bundle` action takes the follwoing parameters:
  - repo: The github repo of the bundle
  - branch (optional): The branch of the github repo where the bundle is.
  - bundle-name: The name of the bundle
  - controller: Name of the controller to use for running the tests

This action will create two Jenkins jobs. The first one will grab
the repository with your bundle, read the bundle.yaml and see if there are
any charms that can be updated. The second job will additionally
update the bundle.yaml and run all the tests of the bundle.
If the tests are successful this job could also release the bundle
and the charms to the store.
The first job will run periodically (every 10 minutes); the second job
is triggered by the first job.

This action requires you to have a `ci-info.yaml` file in your bundle repository.
Here is an example of how that yaml should look like:

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

    juju run-action cwr/0 build-bundle \
      repo=https://github.com/juju-solutions/bundle-cwr-ci \
      branch=build-bundle  \
      bundle-name=cwr-ci \
      controller=lxd


# Resources

- [Juju mailing list](https://lists.ubuntu.com/mailman/listinfo/juju)
- [Juju community](https://jujucharms.com/community)
- [Jenkins](https://jenkins.io/)
