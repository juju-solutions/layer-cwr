import os


def get_controllers():
    controllers_file_path = "/var/lib/jenkins/controller.names"
    controllers = []
    if os.path.exists(controllers_file_path):
        controllers = [line.rstrip('\n') for line in open(controllers_file_path)]

    return controllers
