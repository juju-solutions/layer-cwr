#!/usr/bin/env python3
import time
from jenkins import Jenkins, NotFoundException


def wait_result(jclient, job_name, build_number, secs_to_wait=60):
    timeout = time.time() + secs_to_wait
    while True:
        time.sleep(5)
        if time.time() > timeout:
            raise Exception("Job timeout")
        try:
            build_info = jclient.get_build_info(job_name, build_number)
            if build_info["result"] == 'FAILURE':
                outcome = 'fail'
            else:
                outcome = 'success'

            output = jclient.get_build_console_output(job_name, build_number)
            return outcome, output
        except NotFoundException as e:
            print("Jenkins job {} not running yet".format(build_number))
        except:
            raise
