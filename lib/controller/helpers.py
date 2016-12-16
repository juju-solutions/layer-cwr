import os


CONTROLLERS_LIST_FILE = "/var/lib/jenkins/controller.names"
REST_PORT = 5000
REST_PREFIX = "ci"
REST_VER = "1.0"


def get_controllers():
    controllers_file = CONTROLLERS_LIST_FILE
    controllers = []
    if os.path.exists(controllers_file):
        controllers = [line.rstrip('\n') for line in open(controllers_file)]

    return controllers


def get_rest_path():
    return "/" + REST_PREFIX + "/" + REST_VER
