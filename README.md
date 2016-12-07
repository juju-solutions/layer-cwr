# Overview

This subordinate charm prepares a Jenkins master node to test Juju artifacts (charms and bundles).

# Configuration

This charm needs to know about the available controllers that can be used during tests.

To give the CI access to a controller already bootstrapped you would need to add a user to it and grant permission to add-models:

    juju add-user ciuser
    juju grant ciuser add-model

Then you can call the `register-controller` action. The parameters of this action are the the token you got form the add-user command and a user friendly name for the controller.

    juju run-action cwr/0 register-controller token=<registration_token> name=<controller_name>

Alternatively you can login into jenkins (user admin) and build the `RegisterController` job. To un-register a controller you can call the `unregister-controller` action or you can trigger the `UnregisterController` jenkins job. In both cases you need to provide the user friendly name you appointed to the controller during registration.

To push and release build artifacts to the Juju store directly from the CI you would need to initialize the session between this charm and the store. To do so you can either call the `store-login` action or you can login in to Jenkins and trigger the `InitJujuStoreSession` job. The `store-login` action requires the auth token of already established session. To aquire such token you need to login to the store via the cli (charm login) and then get the base64 representation of the auth token:

    charm login
    .........
    export TOKEN=`base64 ~/.local/share/juju/store-usso-token`
    juju run-action cwr/0 store-login charmstore-usso-token="$TOKEN"

Should you initialise the session between Jenkins and the Juju store using the Jenkins `InitJujuStoreSession` you will need to enter your credentials in the Jenkins UI.

The session to Juju store will be active while the CI is online. To terminate the session you will need to either run the `store-logout` action or trigger the `LogoutFromJujuStore` job from within Jenkins.


# Using the CI to build your Charms

We provide two actions that assist in wiring your github repository with the CI.

## Build On Commit
If you want the CI to build your charm, test it and (optionally) release it to the Juju you should call the `build-on-commit` action. This action takes the following parameters:
  - repo: The github repo of the charm or top layer
  - charm-name: The name of the charm
  - controller: Name of the controller to use for running the tests

Should you decide to release a charm after a successful test you can also specify:
  - push-to-channel: Channel to be used (eg, edge, beta, candidate, stable)
  - lp-id: The launchpad ID/namespace you want the charm released under (eg cs:~bigdata-dev/mycharm)

An example run of this action might look like this:

    juju run-action cwr/0 build-on-commit repo=https://github.com/sastix/tomee-charm-layer charm-name=apache-tomee  push-to-channel=edge lp-id=kos.tsakalozos controller=lxd

Running this action will result in a new job in Jenkins called `charm-<charmname>` that will poll the repository once every 5 minutes. In case new commits are found bundletester will test your charm and the result will be pushed to the store (again, given you have opted in).

## Build on Release

If you want to drive your releases using tags directly from github you should call the `build-on-release` juju action. This job has the same set of parameters as above but the ending jenkins job will build/test/push your charm only if you add a tag to your github repository.

Combining the two jobs gives you a basic yet powerful CI workflow.

# Resources

- [Juju mailing list](https://lists.ubuntu.com/mailman/listinfo/juju)
- [Juju community](https://jujucharms.com/community)
- [Jenkins](https://jenkins.io/)
