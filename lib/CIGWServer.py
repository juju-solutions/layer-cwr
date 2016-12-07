#!/usr/bin/env python3
import os
import io
import json
from flask import Flask
from flask import request
from jenkins import Jenkins

app = Flask(__name__)

@app.route("/ping")
def ping():
    return "ok"


@app.route("/ci/v1.0/controllers")
def list_controllers():
    controllersfilepath = "/var/lib/jenkins/controller.names"
    controllers = []
    if os.path.exists(controllersfilepath):
        controllers = [line.rstrip('\n') for line in open(controllersfilepath)]
    return json.dumps(controllers)


@app.route("/ci/v1.0/controllers/add/<string:name>")
def add_controller(name):
    token = request.args.get("token")
    jclient = get_jenkins_clinet()
    next_build_number = jclient.get_job_info("RegisterController")['nextBuildNumber']
    params = {'REGISTER_STRING': token,
              'CONTROLLER_NAME': name}
    jclient.build_job("RegisterController",  params)
    return str(next_build_number)


@app.route("/ci/v1.0/build/<string:jobname>/<int:buildid>")
def get_build_info(jobname, buildid):
    jclient = get_jenkins_clinet()
    buildinfo = jclient.get_build_info(jobname, buildid)
    jsonstr = json.dumps(buildinfo, sort_keys=True, separators=(',', ': '))
    return jsonstr


@app.route("/ci/v1.0/build-output/<string:jobname>/<int:buildid>")
def get_build_output(jobname, buildid):
    jclient = get_jenkins_clinet()
    buildinfo = jclient.get_build_console_output(jobname, buildid)
    jsonstr = json.dumps(buildinfo, sort_keys=True, separators=(',', ': '))
    return jsonstr


@app.route("/ci/v1.0/trigger/job/<string:jobname>")
def trigger_job(jobname):
    controller = request.args.get("controller")
    jujuartifact = request.args.get("charmname")
    buildtarget = request.args.get("buildtargetname")

    jclient = get_jenkins_clinet()
    next_build_number = jclient.get_job_info(jobname)['nextBuildNumber']
    params = {'CONTROLER': controller,
              'CHARM_NAME': jujuartifact,
              'BUILD_CHARM_TARGET': buildtarget}
    jclient.build_job(jobname,  params)
    return str(next_build_number)


def get_jenkins_clinet():
    with io.open("/var/lib/jenkins/CIGWServer.properties", 'r') as propertiesfile:
        jenkinsurl = propertiesfile.readline().rstrip('\n')
        jenkinsuser = propertiesfile.readline().rstrip('\n')
        jenkinspass = propertiesfile.readline().rstrip('\n')
    jclient = Jenkins(jenkinsurl, jenkinsuser, jenkinspass)
    return jclient


if __name__ == "__main__":
    app.run(host = "0.0.0.0", port=5000)
