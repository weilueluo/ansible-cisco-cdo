#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Apache License v2.0+ (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

# fmt: off
import requests
import base64
from time import sleep
from ansible_collections.cisco.cdo.plugins.module_utils.api_endpoints import CDOAPI
from ansible_collections.cisco.cdo.plugins.module_utils.api_requests import CDORequests
from ansible_collections.cisco.cdo.plugins.module_utils.devices import FTDModel, FTDMetaData
from ansible_collections.cisco.cdo.plugins.module_utils.common import inventory_count, get_device, get_cdfmc
from ansible_collections.cisco.cdo.plugins.module_utils.common import get_cdfmc_access_policy_list, get_specific_device
from ansible_collections.cisco.cdo.plugins.module_utils.errors import DeviceNotFound, AddDeviceFailure, DuplicateObject, ObjectNotFound


# fmt: on
def new_ftd_polling(module_params: dict, http_session: requests.session, endpoint: str, uid: str):
    """Check that the new FTD specific device has been created before attempting move to the onboarding step"""
    for i in range(module_params.get("retry")):
        try:
            return get_specific_device(http_session, endpoint, uid)
        except DeviceNotFound:
            sleep(module_params.get("delay"))
            continue
    raise AddDeviceFailure(f"Failed to add FTD {module_params.get('device_name')}")


def update_ftd_device(http_session: requests.session, endpoint: str, uid: str, data: dict):
    """Update an FTD object"""
    return CDORequests.put(http_session, f"https://{endpoint}", path=f"{CDOAPI.FTDS.value}/{uid}", data=data)


def add_ftd_ltp(module_params: dict, http_session: requests.session, endpoint: str, ftd_device: FTDModel, fmc_uid: str):
    """Onboard an FTD to cdFMC using LTP (serial number onboarding)"""
    if not inventory_count(
        http_session, endpoint, filter=f"serial:{module_params.get('serial')}"
    ) and not inventory_count(http_session, endpoint, filter=f"name:{module_params.get('serial')}"):
        ftd_device.larType = "CDG"
        ftd_device.name = module_params.get("device_name")
        ftd_device.serial = module_params.get("serial")
        if module_params.get("password"):  # Set the initial admin password
            ftd_device.sseDeviceSerialNumberRegistration = dict(
                initialProvisionData=(
                    base64.b64encode(f'{{"nkey": "{module_params.get("password")}"}}'.encode("ascii")).decode("ascii")
                ),
                sudiSerialNumber=module_params.get("serial"),
            )
        else:  # initial password has already been set by the CLI
            ftd_device.sseDeviceSerialNumberRegistration = dict(
                initialProvisionData=base64.b64encode('{"nkey":""}'.encode("ascii")).decode("ascii"),
                sudiSerialNumber=module_params.get("serial"),
            )

        ftd_device.sseEnabled = True

        new_ftd_device = CDORequests.post(
            http_session, f"https://{endpoint}", path=CDOAPI.DEVICES.value, data=ftd_device.asdict()
        )
        ftd_specific_device = new_ftd_polling(module_params, http_session, endpoint, new_ftd_device["uid"])
        new_ftd_device = get_device(http_session, endpoint, new_ftd_device["uid"])
        CDORequests.put(
            http_session,
            f"https://{endpoint}",
            path=f"{CDOAPI.FTDS.value}/{ftd_specific_device['uid']}",
            data={"queueTriggerState": "SSE_CLAIM_DEVICE"},
        )  # Trigger device claiming
        return new_ftd_device

    else:
        raise DuplicateObject(f"Device with serial number {module_params.get('serial')} exists in tenant")


def add_ftd(module_params: dict, http_session: requests.session, endpoint: str):
    """Add an FTD to CDO via CLI or LTP process"""
    try:
        cdfmc = get_cdfmc(http_session, endpoint)
        cdfmc_specific_device = get_specific_device(http_session, endpoint, cdfmc["uid"])
        access_policy = get_cdfmc_access_policy_list(
            http_session,
            endpoint,
            cdfmc["host"],
            cdfmc_specific_device["domainUid"],
            access_list_name=module_params.get("access_control_policy"),
        )
    except DeviceNotFound as e:
        raise e
    except ObjectNotFound as e:
        raise e

    # TODO: Get these from the fmc collection when it supports cdFMC
    ftd_device = FTDModel(
        name=module_params.get("device_name"),
        associatedDeviceUid=cdfmc["uid"],
        metadata=FTDMetaData(
            accessPolicyName=access_policy["items"][0]["name"],
            accessPolicyUuid=access_policy["items"][0]["id"],
            license_caps=",".join(module_params.get("license")),
            performanceTier=module_params.get("performance_tier"),
        ),
    )
    if module_params.get("onboard_method").lower() == "ltp":
        ftd_device = add_ftd_ltp(module_params, http_session, endpoint, ftd_device, cdfmc["uid"])
        return f"Serial number {module_params.get('serial')} ready for LTP onboarding into CDO"
    else:
        new_device = CDORequests.post(
            http_session, f"https://{endpoint}", path=CDOAPI.DEVICES.value, data=ftd_device.asdict()
        )
        specific_ftd_device = new_ftd_polling(module_params, http_session, endpoint, new_device["uid"])
        update_ftd_device(
            http_session, endpoint, specific_ftd_device["uid"], {"queueTriggerState": "INITIATE_FTDC_ONBOARDING"}
        )
        return CDORequests.get(http_session, f"https://{endpoint}", path=f"{CDOAPI.DEVICES.value}/{new_device['uid']}")
