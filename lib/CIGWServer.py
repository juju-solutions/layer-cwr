from io import open
from json import dumps
from flask import Flask, request
from jenkins import Jenkins
from controller.helpers import get_controllers

app = Flask(__name__)


@app.route("/ping")
def ping():
    return "ok"


#
# Controller operations: list, register, unregister
#
@app.route("/ci/v1.0/controllers")
def list_controllers():
    controllers = get_controllers()
    return dumps(controllers)


@app.route("/ci/v1.0/controllers/add/<string:name>")
def add_controller(name):
    job = "RegisterController"
    token = request.args.get("token")
    jclient = get_jenkins_client()
    next_build_number = jclient.get_job_info(job)['nextBuildNumber']
    params = {'REGISTER_STRING': token,
              'CONTROLLER_NAME': name}
    jclient.build_job(job,  params)
    return str(next_build_number)


@app.route("/ci/v1.0/controllers/remove/<string:name>")
def remove_controller(name):
    job = "UnregisterController"
    jclient = get_jenkins_client()
    next_build_number = jclient.get_job_info(job)['nextBuildNumber']
    params = {'CONTROLLER_NAME': name}
    jclient.build_job(job,  params)
    return str(next_build_number)


#
# Job Status and Output
#
@app.route("/ci/v1.0/build/<string:job_name>/<int:build_id>")
def get_build_info(job_name, build_id):
    jclient = get_jenkins_client()
    build_info = jclient.get_build_info(job_name, build_id)
    return dumps(build_info, sort_keys=True, separators=(',', ': '))


@app.route("/ci/v1.0/build-output/<string:job_name>/<int:build_id>")
def get_build_output(job_name, build_id):
    jclient = get_jenkins_client()
    build_info = jclient.get_build_console_output(job_name, build_id)
    return dumps(build_info, sort_keys=True, separators=(',', ': '))


#
# RunCWR Jenkins Job
#
@app.route("/ci/v1.0/trigger/job/RunCwr")
def trigger_job():
    job = "RunCwr"
    controller = request.args.get("controller")
    juju_artifact = request.args.get("charmname")
    build_target = request.args.get("buildtargetname")

    jclient = get_jenkins_client()
    next_build_number = jclient.get_job_info(job)['nextBuildNumber']
    params = {'CONTROLLER': controller,
              'CHARM_NAME': juju_artifact,
              'BUILD_CHARM_TARGET': build_target}
    jclient.build_job("RunCwr",  params)
    return str(next_build_number)


def get_jenkins_client():
    properties_path = "/var/lib/jenkins/CIGWServer.properties"
    with open(properties_path, 'r') as properties_file:
        jenkins_url = properties_file.readline().rstrip('\n')
        jenkins_user = properties_file.readline().rstrip('\n')
        jenkins_pass = properties_file.readline().rstrip('\n')
    jclient = Jenkins(jenkins_url, jenkins_user, jenkins_pass)
    return jclient


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
