# Juju collectd subordinate charm

This subordinate charm will deploy collectd daemon

By default metrics are not forwarded or exposed in any way
but that can be achieved using configuration options

Optionally the charm can expose metrics for prometheus scraping.
This requires `canonical-bootstack-collectd-exporter` package to
be available for installation

## How to deploy the charm

The charm relates with any principal charm using juju-info interface.
Assuming that the principal service is called `ubuntu` and have a copy
of collectd subordinate in `charms/$distrocodename/collectd` relative
to your current directory.

... then to perform a deployment execute the following steps:

    juju deploy --repository=charms local:trusty/collectd collectd
    # and 
    juju add-relation ubuntu collectd

To send metrics to the graphite server listening on 192.168.99.10 port 2003:

    juju set collectd graphite_endpoint=192.168.99.10:2003

To expose metrics for prometheus on port 9103 under "/metrics" URL:
    juju set collectd prometheus_export=http://127.0.0.1:9103/metrics

See config.yaml for more details about configuration options

## Development

Branch code to:

    $JUJU_REPOSITORY/layers/collectd/

Modify

Assemble the charm:

    charm compose
