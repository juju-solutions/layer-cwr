import os

CONTROLLERS_LIST_FILE = "/var/lib/jenkins/controller.names"


def get_controllers():
    controllers_file = CONTROLLERS_LIST_FILE
    controllers = []
    if os.path.exists(controllers_file):
        controllers = [line.rstrip('\n') for line in open(controllers_file)]

    return controllers
