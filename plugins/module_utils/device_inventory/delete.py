#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Apache License v2.0+ (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

# fmt: off
from ansible_collections.cisco.cdo.plugins.module_utils.api_endpoints import CDOAPI
from ansible_collections.cisco.cdo.plugins.module_utils.api_requests import CDORequests
from ansible_collections.cisco.cdo.plugins.module_utils.common import working_set, get_cdfmc, get_specific_device, gather_inventory
from ansible_collections.cisco.cdo.plugins.module_utils.errors import DeviceNotFound, TooManyMatches
import requests
# fmt: on


def find_device_for_deletion(module_params: dict, http_session: requests.session, endpoint: str):
    """Find the object we intend to delete"""
    module_params["filter"] = module_params.get("device_name")
    device_list = gather_inventory(module_params, http_session, endpoint)
    if len(device_list) < 1:
        raise DeviceNotFound(f"Cannot delete {module_params.get('device_name')} - device by that name not found")
    elif len(device_list) > 1:
        raise TooManyMatches(f"Cannot delete {module_params.get('device_name')} - more than 1 device matches name")
    else:
        return device_list[0]


def delete_device(module_params: dict, http_session: requests.session, endpoint: str):
    """Orchestrate deleting the device"""
    try:
        device = find_device_for_deletion(module_params, http_session, endpoint)
        working_set(http_session, endpoint, device["uid"])
        if module_params.get("device_type").upper() == "ASA" or module_params.get("device_type").upper() == "IOS":
            response = CDORequests.delete(
                http_session, f"https://{endpoint}", path=f"{CDOAPI.DEVICES.value}/{device['uid']}"
            )
            return response

        elif module_params.get("device_type").upper() == "FTD":
            cdfmc = get_cdfmc(http_session, endpoint)
            cdfmc_specific_device = get_specific_device(http_session, endpoint, cdfmc["uid"])
            data = {
                "queueTriggerState": "PENDING_DELETE_FTDC",
                "stateMachineContext": {"ftdCDeviceIDs": f"{device['uid']}"},
            }
            response = CDORequests.put(
                http_session,
                f"https://{endpoint}",
                path=f"{CDOAPI.FMC.value}/{cdfmc_specific_device['uid']}",
                data=data,
            )
            return response
    except DeviceNotFound as e:
        raise e
