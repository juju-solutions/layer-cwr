#!/usr/bin/env python3
from charmhelpers.core import hookenv
from charms.reactive import RelationBase
from jenkins import Jenkins


def add_job():
    jenkins_relation = (RelationBase.from_state('jenkins.available'))
    jenkins_connection_info = jenkins_relation.get_connection_info()
    jclient = Jenkins(jenkins_connection_info["jenkins_url"],
                      jenkins_connection_info["admin_username"],
                      jenkins_connection_info["admin_password"])

    gitrepo = hookenv.action_get("gitrepo")
    pushtochannel = hookenv.action_get("pushtochannel")
    branch = "*/tags/*"
    lpid = hookenv.action_get("lpid")
    charmname = hookenv.action_get("charmname")
    controller = hookenv.action_get("controller")
    refspec = "<refspec>+refs/tags/*:refs/remotes/origin/tags/*</refspec>"

    rep = {"{{gitrepo}}": gitrepo,
           "{{pushtochannel}}": pushtochannel,
           "{{lpid}}": lpid,
           "{{branch}}": branch,
           "{{charmname}}": charmname,
           "{{refspec}}": refspec,
           "{{controller}}": controller}

    template_path_source = "templates/BuildMyCharm/config.xml"
    with open(template_path_source) as infile:
        data = infile.read()
        for src, target in rep.items():
            data = data.replace(src, target)
        jclient.create_job("release-charm-{}".format(charmname), data)


if __name__ == "__main__":
    add_job()
