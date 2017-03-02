#!/bin/bash

set -e


function add_exit_handler() {
    handler="$1"
    old_trap=`trap -p EXIT | awk -F"'" '{print $2}'`
    trap "$handler ; $old_trap" EXIT
}


function skip_builds() {
    if [ ! -f "first-run.lock" ]; then
        touch "first-run.lock"
        echo "First run automatically triggered. Skipped."
        touch results.xml
        exit 0
    fi

    if test `find "first-run.lock" -mmin -1`
    then
        echo "Skip build. Caused by tag already present in repo."
        touch results.xml
        exit 0
    fi
}


function checkout_release_tag() {
    if [ ! -z $RELEASE_TAG ]
    then
        echo "Moving to release tag $RELEASE_TAG"
        git checkout $RELEASE_TAG
    fi
}


function checkout_pull_request() {
    echo "Checking out pull request $PR_ID"
    git fetch origin pull/$PR_ID/head:prtotest$BUILD_NUMBER
    git checkout prtotest$BUILD_NUMBER
}


function check_container_network() {
    lxc info $1 | grep -qE 'eth0:\sinet\s'
}


function update_image() {
    tmp_dir=$(mktemp -dt cwrbox.XXXXXXXX)
    url_file='/var/lib/jenkins/cwrbox_image.url'
    cur_sig_file='/var/lib/jenkins/cwrbox.tar.gz.sig'
    new_img_file="$tmp_dir/cwrbox.tar.gz"
    new_sig_file="$tmp_dir/cwrbox.tar.gz.sig"

    add_exit_handler "rm -rf $tmp_dir"

    if [[ ! -e $url_file ]]; then
        echo "Using cwrbox image from attached resource"
        return 0
    fi

    img_url=$(cat $url_file)
    sig_url="${img_url}.sig"

    echo "Fetching remote cwrbox image signature"
    if ! wget -qO $new_sig_file $sig_url; then
        >&2 echo "Failed to fetch cwrbox image signature"
    fi
    if [[ -f $cur_sig_file ]] && cmp -s $cur_sig_file $new_sig_file; then
        >&2 echo "No new cwrbox image available"
        return
    fi
    echo "Fetching remote cwrbox image"
    if ! wget -qO $new_img_file $img_url; then
        >&2 echo "Failed to fetch cwrbox image"
        exit 1
    fi
    echo "Verifying cwrbox image against signature"
    if ! gpgv2 --keyring cwrbox.gpg $new_sig_file $new_img_file; then
        >&2 echo "Failed to verify cwrbox image"
        exit 1
    fi
    echo "Importing cwrbox image"
    if ! lxc image import $new_img_file --alias cwrbox; then
        >&2 echo "Failed to import cwrbox image"
        exit 1
    fi
    mv -f $new_sig_file $cur_sig_file
}


function run_in_container() {
    container=$(petname)
    echo "Creating container"
    lxc init cwrbox $container
    add_exit_handler "lxc delete --force $container"

    echo "Configuring container"
    # map container's root to jenkins
    lxc config set $container raw.idmap "$(printf "uid $(id -u) 0\ngid $(id -g) 0")"

    # Copy in Juju config (instead of mounting to isolate active model) and helper scripts
    lxc file push -r ~/.local/share/juju $container/root/.local/share/
    lxc file push -r /var/lib/jenkins/scripts/ $container/usr/local/bin/

    # Mount the workspace and artifacts dir
    lxc config device add $container workspace disk source=$(pwd) path=/root/workspace
    lxc config device add $container artifacts disk source=/srv/artifacts path=/srv/artifacts

    # buildbundle.py does fetching and processing outside of the container
    # we should refactor that so that the tools (bundletester and/or matrix)
    # have a defined way of specifying overrides for CI and everything can
    # be done in the container and in a consistent way; for now, mount it into
    # the container so that CWR can access it
    bundle="$5"  # fragile and encapsulation breaking :(
    if [[ "$bundle" == "/tmp/"* ]]; then
        lxc config device add $container bundle disk source="$bundle" path="$bundle"
    fi

    echo "Starting container"
    lxc start $container

    echo "Waiting for container's networking to come up"
    wait_time=1
    until check_container_network $container || [[ $wait_time == 30 ]]; do
        sleep 1
        wait_time=$(( wait_time + 1 ))
    done
    if ! check_container_network $container; then
        >&2 echo 'Container does not have network connectivity'
        exit 1
    fi

    echo "Freshening container"
    lxc exec $container -- apt update -yq

    # Run the command.
    echo "Execing container"
    lxc exec $container --env=JOB_NAME="$JOB_NAME" \
                        --env=WORKSPACE="/root/workspace" \
                        --env=BUILD_NUMBER="$BUILD_NUMBER" \
                        --env=TOKEN="$TOKEN" \
                        --env=REPO="$REPO" \
                        --env=PR_ID="$PR_ID" \
                        -- "$@"
}

function build_charm() {
    charm_name="$1"
    series="$2"
    charm_subdir="$3"
    export JUJU_REPOSITORY="/tmp"
    output_dir="builds"
    series_flag=""
    if [[ -n "$series" ]]; then
        output_dir="$series"
        series_flag="--series $series"
    fi

    mkdir -p $JUJU_REPOSITORY/$output_dir
    rm -rf $JUJU_REPOSITORY/$output_dir/$charm_name

    if [[ -f "workspace/$charm_subdir/layer.yaml" ]]; then
        charm build $series_flag "workspace/$charm_subdir"
    else
        cp -a "workspace/$charm_subdir" $JUJU_REPOSITORY/$output_dir/$charm_name
    fi
}


function fetch_bundle() {
    bundle="$1"
    bundle_fname="$(get_fname $bundle)"
    [ -e /tmp/bundles ] || mkdir /tmp/bundles
    rm -rf /tmp/bundles/$bundle_fname
    charm pull "$bundle" /tmp/bundles/$bundle_fname
}


function get_fname() {
    echo $1 | sed -e 's/[^a-zA-Z0-9]/_/g'
}


function job_output_dir() {
    job_title=$(get_fname $1)
    echo /srv/artifacts/${job_title}/$BUILD_NUMBER
}


function link_artifacts() {
    artifacts_dir=$(job_output_dir "$1")
    ln -s $artifacts_dir /var/lib/jenkins/jobs/$JOB_NAME/builds/$BUILD_NUMBER/archive
}


function copy_xml() {
    artifacts_dir=$(job_output_dir "$1")
    cp -f $artifacts_dir/report.xml $WORKSPACE/report.xml
}


function release_charm() {
  # Push a directory to the charm store, release it and grant everyone access.
  local charm_build_dir=$1
  shift
  local lp_id=$1
  shift
  local series=$1
  shift
  local charm_name=$1
  shift
  local channel=$1
  shift

  # The series is optional, check the third parameter for non empty string.
  if [[ -n "${series}" ]]; then
    local charm_id="cs:~${lp_id}/${series}/${charm_name}"
  else
    local charm_id="cs:~${lp_id}/${charm_name}"
  fi

  local channel_flag=""
  # The channel is optional, check the fifth parameter for non empty string.
  if [[ -n "${channel}" ]]; then
    channel_flag="--channel=${channel}"
  fi

  local resources=""
  # Loop through the remaining parameter for potentially multiple resources.
  for resource in "$@"; do
    # Resources should be in the name=value touple per parameter.
    resources="${resources} --resource ${resource}"
  done

  # Build the charm push command from the variables.
  local push_cmd="charm push ${charm_build_dir} ${charm_id} ${resources}"
  # Run the push command and capture the id of the pushed charm.
  local pushed_charm=`${push_cmd} | head -1 | awk '{print $2}'`
  # Release the charm to the specific channel.
  charm release ${pushed_charm} ${channel_flag}
  # Grant everyone read access to this charm in channel.
  charm grant ${pushed_charm} ${channel_flag} everyone
}


function add_models() {
    # Keep track of the controllers and models we want CWR to run
    # If not specified, CWR will run on all registered controllers
    controllers="${@:-$(cat /var/lib/jenkins/controller.names)}"
    MODELS_TO_TEST=""

    petname=$(petname)
    for controller in $controllers
    do
        juju switch $controller

        # we have to figure out which credential to use because of:
        # https://bugs.launchpad.net/juju/+bug/1652171
        cloud=$(juju add-model wont-be-added --credential invalid-credential 2>&1 | sed -e 's/.*cloud "\?\([^ "]*\)"\?.*/\1/')
        credential_arg=""
        if [[ "$cloud" != "localhost" && "$cloud" != "lxd" ]]; then
            if ! juju credentials --format=json | grep -q $cloud; then
                echo 'This cloud requires a credential which was not found.'
                echo 'Please use set-credentials to add the credential.'
                exit 1
            fi
            credential=$(juju credentials --format=json | jq -r '.credentials.'${cloud}'."cloud-credentials" | keys[0]')
            credential_arg="--credential=$credential"
        fi

        model_name=$petname-$BUILD_NUMBER
        juju add-model $model_name $credential_arg
        juju model-config -m $model_name test-mode=true
        juju grant admin admin $model_name || true

        # Keep track of all the models we want CWR to test
        MODELS_TO_TEST+="${controller}:${model_name} "
    done

    function cleanup_models() {
        for model in $MODELS_TO_TEST; do
            juju destroy-model $model -y
        done
    }
    add_exit_handler cleanup_models

    sleep 5 # temporary hackaround for https://bugs.launchpad.net/juju/+bug/1635052

    export MODELS_TO_TEST
}


function run_cwr() {
    models="$1"
    job_title="$2"
    bundle_name="$3"
    bundle_fname="$(get_fname $bundle_name)"
    charm_name="$4"
    charm_fname="$(get_fname $charm_name)"
    series="$5"
    app_name_in_bundle="$6"
    charm_subdir="$7"
    push_to_channel="$8"
    lp_id="$9"
    charm_build_dir="/tmp/${series:-builds}/$charm_name"

    if [[ -n "$charm_name" ]]; then
        build_charm "$charm_name" "$series" "$charm_subdir"
        fetch_bundle "$bundle_name"
        cwr-update-bundle.py "$bundle_fname" "$app_name_in_bundle" "$charm_build_dir"
        bundle="/tmp/bundles/$bundle_fname"
        bundle_file="bundle-cwr.yaml"
    else
        bundle="$bundle_name"
        bundle_file="bundle.yaml"
    fi

    rm -f totest.yaml
    echo "bundle: $bundle" >> totest.yaml
    echo "bundle_name: $job_title" >> totest.yaml
    echo "bundle_file: $bundle_file" >> totest.yaml

    artifacts_dir=$(job_output_dir "$job_title")
    if ! env MATRIX_OUTPUT_DIR=$artifacts_dir cwr -F -l DEBUG -v $models totest.yaml --results-dir /srv/artifacts --test-id $BUILD_NUMBER
    then
        echo 'CWR reported failure'
        if [[ -n $PR_ID && -n $TOKEN ]]; then
            send-comment.py $TOKEN $REPO $PR_ID "PR failed Cloud Weather Report tests"
        fi
        exit 1
    fi

    echo 'CWR reported success'
    if [[ -n $PR_ID && -n $TOKEN ]]; then
        send-comment.py $TOKEN $REPO $PR_ID "PR passed Cloud Weather Report tests"
    fi

    if [[ $? == 0 && -n "$push_to_channel" && -n "$lp_id" ]]; then
        release_charm $charm_build_dir $lp_id $series $charm_name $push_to_channel
    fi
}


function run_cwr_in_container() {
    controllers="$1"
    shift 1  # remove controllers, pass through other args
    job_title="$1"
    bundle_name="$2"
    charm_name="$3"
    series="$4"
    app_name_in_bundle="$5"
    charm_subdir="$6"
    push_to_channel="$7"
    lp_id="$8"

    artifacts_dir=$(job_output_dir "$job_title")
    mkdir -p $artifacts_dir

    add_exit_handler "link_artifacts $job_title"
    add_exit_handler "copy_xml $job_title"

    update_image

    add_models $controllers

    if [[ -n "$OUTPUT_SCENARIO" ]]
    then
         FAKE_FILES_TAR="/var/lib/jenkins/mock-results/$OUTPUT_SCENARIO.tar.gz";
         tar -zxvf $FAKE_FILES_TAR -C $ARTIFACTS_DIR

         if [[ $OUTPUT_SCENARIO == pass* ]]
         then
             exit 0
         else
             exit 1
         fi
    else
        run_in_container cwr-helpers.sh run_cwr "$MODELS_TO_TEST" "$@"
    fi
}


cmd=$1
if [[ -n "$1" ]]; then
    shift
    case $cmd in
        run_cwr)
            run_cwr "$@" ;;
        run_cwr_in_container)
            run_cwr_in_container "$@" ;;
    esac
fi
