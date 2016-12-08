# Overview

This subordinate charm prepares a Jenkins master node to test Juju artifacts (charms and bundles).

# Configuration

This charm needs to know about the available controllers that can be used during tests.

To give the CI access to a controller already bootstrapped you would need to add a user to it and grant permission to add-models:

    juju add-user ciuser
    juju grant ciuser add-model

Then login into jenkins (user admin) and build the `RegisterController` job providing the token you got form the add-user command and a user friendly name for the controller. To un-register a controller you need to trigger the `UnregisterController` job and provide the user friendly name you appointed to it during registration.

While you are logged in to Jenkins you can initialise the session between Jenkins and the Juju Store so that you can push the build artifacts to the store. To do so you need to trigger the `InitJujuStoreSession` job. The session to Juju Store will be active while the CI is online. To terminate the session you will need to trigger the `LogoutFromJujuStore` job.


# Using the CI to build your Charms

We provide two actions that assist in wiring your github repository with the CI.

## Build On Commit
If you want the CI to build your charm, test it and (optionally) release it to the Juju you should call the `buildcharmoncommit` action. This action takes the following parameters:
  - githubrepo: The github repo of the charm or top layer
  - charmname: The name of the charm
  - controller: Name of the controller to use for running the tests

Should you decide to release a charm after a successful test you can also specify:
  - pushtochannel: Channel to be used (eg, edge, beta, candidate, stable)
  - lpid: The launchpad ID/namespace you want the charm released under (eg cs:~bigdata-dev/mycharm)

An example run of this action might look like this:

    juju run-action jce8/0 buildcharmoncommit gitrepo=https://github.com/sastix/tomee-charm-layer charmname=apache-tomee  pushtochannel=edge lpid=kos.tsakalozos controller=lxd

Running this action will result in a new job in Jenkins called `charm-<charmname>` that will poll the repository once every 5 minutes. In case new commits are found bundletester will test your charm and the result will be pushed to the store (again, given you have opted in).

## Build on Release

If you want to drive your releases using tags directly from github you should call the `buildcharmonrelease` juju action. This job has the same set of parameters as above but the ending jenkins job will build/test/push your charm only if you add a tag to your github repository.

Combining the two jobs gives you a basic yet powerful CI workflow.

# Resources

- [Juju mailing list](https://lists.ubuntu.com/mailman/listinfo/juju)
- [Juju community](https://jujucharms.com/community)
- [Jenkins](https://jenkins.io/)
