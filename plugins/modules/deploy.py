#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Apache License v2.0+ (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)


from __future__ import absolute_import, division, print_function

__metaclass__ = type


DOCUMENTATION = r"""
---
module: deploy

short_description: Check for changes and deploy to devices (FTD, ASA, IOS devices) on Cisco Defense Orchestrator (CDO).

version_added: "1.0.3"

description: This module is to read inventory (FTD, ASA, IOS devices) on Cisco Defense Orchestrator (CDO).
options:
    api_key:
        type: str
        required: true
        no_log: true
    region:
        type: str
        choices: [us, eu, apj]
        default: us
    deploy:
        device_type:
            type: str
            required: False
            choices: [asa, ios, ftd, all]
            default: "all"
    pending:
        device_type:
            type: str
            required: False
            choices: [asa, ios, ftd, all]
            default: "all"

author:
    - Aaron Hackney (@aaronhackney)
"""

EXAMPLES = r""" """

# fmt: off
import requests
import time
from time import sleep
from ansible_collections.cisco.cdo.plugins.module_utils.api_endpoints import CDOAPI
from ansible_collections.cisco.cdo.plugins.module_utils.api_requests import CDORegions, CDORequests
from ansible_collections.cisco.cdo.plugins.module_utils._version import __version__
from ansible_collections.cisco.cdo.plugins.module_utils.args_common import (
    DEPLOY_ARGUMENT_SPEC,
    DEPLOY_MUTUALLY_REQUIRED_ONE_OF,
    DEPLOY_MUTUALLY_EXCLUSIVE,
    DEPLOY_REQUIRED_IF
)
from ansible_collections.cisco.cdo.plugins.module_utils.query import CDOQuery
from ansible_collections.cisco.cdo.plugins.module_utils.common import gather_inventory
from ansible_collections.cisco.cdo.plugins.module_utils.errors import DeviceNotFound, TooManyMatches, APIError, CredentialsFailure
from ansible.module_utils.basic import AnsibleModule
# fmt: on

# TODO: Document and Link with cdFMC Ansible module to deploy staged FTD configs


def poll_deploy_job(http_session: requests.session, endpoint: str, job_uid: str, retry, interval):
    """Poll the doplay job for a successful completion"""
    while retry > 0:
        job_status = CDORequests.get(http_session, f"https://{endpoint}", path=f"{CDOAPI.JOBS.value}/{job_uid}")
        state_uid = job_status.get("objRefs")[0].get("uid")
        if job_status.get("stateMachinesProgress").get(state_uid).get("progressStatus") == "DONE":
            return job_status
        sleep(interval)
        retry -= 1


def deploy_changes(module_params: dict, http_session: requests.session, endpoint: str):
    """Given the device name, deploy the pending config changes to the device if there are any"""

    # Check to see if there are any pending changes before deploying unnecessarily
    q = CDOQuery.pending_changes_query(module_params, agg=True)
    count = CDORequests.get(http_session, f"https://{endpoint}", path=f"{CDOAPI.DEPLOY.value}", query=q).get(
        "aggregationQueryResult"
    )
    if not count:
        return

    # collect the pending changes before deployment
    pending_config = get_pending_deploy(module_params, http_session, endpoint)

    # Deploy the pending config
    module_params["filter"] = module_params.get("device_name")
    device = gather_inventory(module_params, http_session, endpoint)
    if len(device) == 0:
        raise (DeviceNotFound(f"Could not find device {module_params.get('device_name')}"))
    elif len(device) == 0:
        raise (TooManyMatches(f"{len(device)} matched - {module_params.get('device_name')} not a unique device name"))
    payload = {
        "action": "WRITE",
        "overallProgress": "PENDING",
        "triggerState": "PENDING_ORCHESTRATION",
        "schedule": None,
        "objRefs": [{"uid": device[0].get("uid"), "namespace": "targets", "type": "devices"}],
        "jobContext": None,
    }

    # Submit the job then return the completed job details after polling for deploy completion
    job = CDORequests.post(http_session, f"https://{endpoint}", path=f"{CDOAPI.JOBS.value}", data=payload)

    return {
        "deploy_job": poll_deploy_job(
            http_session, endpoint, job.get("uid"), module_params.get("timeout"), module_params.get("interval")
        ),
        "changes_deployed": pending_config,
    }


def get_pending_deploy(module_params: dict, http_session: requests.session, endpoint: str) -> str:
    """Given a device name, return the config staged in CDO to be deployed, if any"""
    pending_change = list()
    q = CDOQuery.pending_changes_query(module_params)
    result = CDORequests.get(http_session, f"https://{endpoint}", path=f"{CDOAPI.DEPLOY.value}", query=q)
    for item in result:
        staged_config = dict()
        staged_config["device_uid"] = item.get("changeLogInstance").get("objectReference").get("uid")
        staged_config["device"] = item.get("changeLogInstance").get("name")
        staged_config["diff"] = list()
        for event in item.get("changeLogInstance").get("events"):
            event.get("details").pop("_class")
            staged_config["diff"].append(event.get("details"))
            staged_config["user"] = event.get("user")
            staged_config["date"] = (
                time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(int(event.get("eventDate")) / 1000.0)) + " UTC"
            )
            staged_config["action"] = event.get("action")
        pending_change.append(staged_config)
    return pending_change


def main():
    result = dict(msg="", stdout="", stdout_lines=[], stderr="", stderr_lines=[], rc=0, failed=False, changed=False)
    module = AnsibleModule(
        argument_spec=DEPLOY_ARGUMENT_SPEC,
        required_one_of=[DEPLOY_MUTUALLY_REQUIRED_ONE_OF],
        mutually_exclusive=DEPLOY_MUTUALLY_EXCLUSIVE,
        required_if=DEPLOY_REQUIRED_IF,
    )

    endpoint = CDORegions.get_endpoint(module.params.get("region"))
    http_session = CDORequests.create_session(module.params.get("api_key"), __version__)

    # Deploy pending configuration changes to specific device
    if module.params.get("deploy"):
        try:
            deploy = deploy_changes(module.params.get("deploy"), http_session, endpoint)
            result["stdout"] = deploy
            if result["stdout"]:
                result["changed"] = True
        except (DeviceNotFound, TooManyMatches, APIError, CredentialsFailure) as e:
            result["stderr"] = f"ERROR: {e.message}"

    # Get pending changes for devices
    if module.params.get("pending"):
        try:
            pending_deploy = get_pending_deploy(module.params.get("pending"), http_session, endpoint)
            result["stdout"] = pending_deploy
        except (DeviceNotFound, APIError, CredentialsFailure) as e:
            result["stderr"] = f"ERROR: {e.message}"

    module.exit_json(**result)


if __name__ == "__main__":
    main()
