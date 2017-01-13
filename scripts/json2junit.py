#!/usr/bin/env python3
import sys
import json
import xml
from pprint import pprint
from xml.etree.ElementTree import Element, SubElement, tostring
import xml.dom.minidom


if __name__ == "__main__":
    if "--help" in sys.argv or len(sys.argv) == 0:
        print("Usage: {} <results_path> <artifact> <build_id>\n".format(sys.argv[0]))
        print("  <results_path>: cwr results directory.")
        print("  <artifact>: bundle or charm name.")
        print("  <build_id>: Id of the build to export to xUnit.")
        sys.exit(1)
    results_dir = sys.argv[1]
    item_name = sys.argv[2]
    build_id = sys.argv[3]

    json_filename = "{}/{}/{}/report.json".format(results_dir, item_name, build_id)
    with open(json_filename, 'r') as json_fp:
        data = json.load(json_fp)

    top = Element('testsuites')
    for suite in data['results']:
        testsuitename = "{}".format(suite['provider'])
        testsuite = SubElement(top, 'testsuite', {"name": testsuitename, "tests": "{}".format(len(suite['tests']))})

        for test in suite['tests']:
            testcase = SubElement(testsuite, 'testcase',
                                  {"name": test['name'],
                                   "classname": test['suite'],
                                   "time": "{}".format(test['duration'])})
            if test['result'] != 'PASS':
                type = 'error' if test['result'] == 'FAIL' else 'failure'
                errorelement = SubElement(testcase, type, {"message": test['output']})
                errorelement.text = test['output']
            else:
                okelement = SubElement(testcase, 'system-out')
                okelement.text = test['output']

    xmlstr = tostring(top, encoding="utf-8")
    xml = xml.dom.minidom.parseString(xmlstr)
    pretty_xml_as_string = xml.toprettyxml()
    print(pretty_xml_as_string)
