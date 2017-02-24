from json import dumps, loads
from flask import Flask, request, abort, make_response
from jenkins import Jenkins
from pathlib import Path
import mimetypes
import logging

import sys
sys.path.append('../lib')

from charmhelpers.core import templating  # noqa: E402
from utils import (
    REST_PORT,
    get_controllers,
    get_rest_path,
    get_badge_path,
    validate_hook_token
)  # noqa: E402


logging.basicConfig(filename='/var/log/cwr-server/cwr-server.log',
                    level=logging.INFO)

app = Flask(__name__)
rest_path = get_rest_path()


def json_response(data):
    return (
        dumps(data, sort_keys=True, separators=(',', ': ')),
        {'Content-Type': 'application/json'},
    )


@app.route("/ping")
def ping():
    return "ok"


#
# Controller operations: list, register, unregister
#
@app.route(rest_path + "/controllers")
def list_controllers():
    controllers = get_controllers()
    return dumps(controllers)


@app.route(rest_path + "/controllers/add/<string:name>")
def add_controller(name):
    job = "RegisterController"
    token = request.args.get("token")
    jclient = get_jenkins_client()
    next_build_number = jclient.get_job_info(job)['nextBuildNumber']
    params = {'REGISTER_STRING': token,
              'CONTROLLER_NAME': name}
    jclient.build_job(job,  params)
    return str(next_build_number)


@app.route(rest_path + "/controllers/remove/<string:name>")
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
@app.route(rest_path + "/build/<string:job_name>/<int:build_id>")
def get_build_info(job_name, build_id):
    jclient = get_jenkins_client()
    build_info = jclient.get_build_info(job_name, build_id)
    return dumps(build_info, sort_keys=True, separators=(',', ': '))


@app.route(rest_path + "/build-output/<string:job_name>/<int:build_id>")
def get_build_output(job_name, build_id):
    jclient = get_jenkins_client()
    build_info = jclient.get_build_console_output(job_name, build_id)
    return dumps(build_info, sort_keys=True, separators=(',', ': '))


@app.route(get_badge_path("<string:job_name>"))
def get_build_svg_output(job_name):
    job_path = Path('/srv/artifacts') / job_name
    report_file = None
    if job_path.exists():
        last_build = sorted(d for d in job_path.iterdir() if d.is_dir())[-1]
        report_file = last_build / 'report.json'
    templates_dir = str(Path(__file__).parent.parent / 'templates')

    # We might not have a first build yet
    if not report_file or not report_file.exists():
        context = {'results': []}
    else:
        context = loads(report_file.read_text())

    results_args = request.args.get("results")
    if results_args:
        # allow overriding results for testing
        context['results'] = []
        for arg in results_args.split('_'):
            provider, test_outcome = arg.split('-')
            context['results'].append({
                'provider': provider,
                'test_outcome': test_outcome})

    svg = templating.render(source='badge.svg',
                            target=None,
                            templates_dir=templates_dir,
                            context=context)

    response = make_response(svg)
    response.content_type = 'image/svg+xml'
    return response


@app.route(rest_path + "/build-artifacts/<string:job_name>/<int:build_id>/")
@app.route(rest_path + "/build-artifacts/<string:job_name>/<int:build_id>/"
           "<string:filename>")
def get_build_artifact(job_name, build_id, filename=None):
    charm_name = build_id[len('charm-'):]
    if filename:
        return frontend('/'.join([charm_name, build_id, filename]))
    else:
        files = [p.name for p in
                 (Path('/srv/artifacts') / charm_name / build_id).iterdir()]
        return json_response(files)


#
# RunCWR Jenkins Job
#
@app.route(rest_path + "/trigger/job/RunCwr")
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


#
# Trigger job based on id
#
@app.route(rest_path + "/trigger/<string:job>/<string:token>",
           methods=['POST'])
def trigger_job_from_webhook(job, token):

    if not validate_hook_token(job, token):
        abort(400)

    if request.headers.get('X-GitHub-Event') == 'ping':
        return "pong"

    datastr = request.form['payload']
    data = loads(datastr)
    if data and "release" in data:
        tag_name = data['release']['tag_name']
    else:
        tag_name = ""

    if request.headers.get('X-GitHub-Event') == 'release' and tag_name == '':
        abort(400)

    jclient = get_jenkins_client()
    next_build_number = jclient.get_job_info(job)['nextBuildNumber']
    if job.startswith("charm_"):
        jclient.build_job(job, {'RELEASE_TAG': tag_name})
    else:
        jclient.build_job(job)
    return str(next_build_number)


#
# Trigger job for testing a PR based on cwr job id
#
@app.route(rest_path + "/pr-trigger/<string:job>/<string:token>",
           methods=['POST'])
def trigger_pr_job_from_webhook(job, token):

    if not validate_hook_token(job, token):
        abort(400)

    if request.headers.get('X-GitHub-Event') == 'ping':
        return "pong"

    datastr = request.form['payload']
    data = loads(datastr)
    if data['action'] not in ['opened', 'synchronize']:
        return "Action {} does not require CWR testing".format(data['action'])

    jclient = get_jenkins_client()
    next_build_number = jclient.get_job_info(job)['nextBuildNumber']
    jclient.build_job(job, {'PR_ID': data['number']})
    return str(next_build_number)


@app.route("/")
@app.route("/<path:filepath>")
def frontend(filepath=None):
    """
    This serves the CWR pages directly, and is intended as the end-user view.

    Note that it must come last as it has a catch-all path argument that would
    conflict with the API views.
    """
    if not filepath:
        filepath = 'index.html'
    fullpath = Path('/srv/artifacts') / filepath
    if not fullpath.is_file():
        abort(404)
    fullpath = fullpath.resolve()
    if not str(fullpath).startswith('/srv/artifacts/'):
        abort(404)
    content_type, _ = mimetypes.guess_type(filepath)
    if not content_type:
        content_type = 'application/octet-stream'
    contents = fullpath.read_bytes()
    return contents, {'Content-Type': content_type}


def get_jenkins_client():
    properties_path = "/var/lib/jenkins/CIGWServer.properties"
    with open(properties_path, 'r') as properties_file:
        jenkins_url = properties_file.readline().rstrip('\n')
        jenkins_user = properties_file.readline().rstrip('\n')
        jenkins_pass = properties_file.readline().rstrip('\n')
    jclient = Jenkins(jenkins_url, jenkins_user, jenkins_pass)
    return jclient


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=REST_PORT)
