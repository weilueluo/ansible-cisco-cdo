#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Apache License v2.0+ (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import urllib.parse


class CDOQuery:
    """Helpers for building complex inventory queries"""

    @staticmethod
    def get_inventory_query(module_params: dict) -> dict:
        """Build the inventory query based on what the user is looking for"""
        device_type = module_params.get("device_type")
        filter = module_params.get("filter")
        r = (
            "[targets/devices.{name,customLinks,healthStatus,sseDeviceRegistrationToken,"
            "sseDeviceSerialNumberRegistration,sseEnabled,sseDeviceData,state,ignoreCertificate,deviceType,"
            "configState,configProcessingState,model,ipv4,modelNumber,serial,chassisSerial,hasFirepower,"
            "connectivityState,connectivityError,certificate,mostRecentCertificate,tags,tagKeys,type,"
            "associatedDeviceUid,oobDetectionState,enableOobDetection,deviceActivity,softwareVersion,"
            "autoAcceptOobEnabled,oobCheckInterval,larUid,larType,metadata,fmcApplianceIpv4,lastDeployTimestamp}]"
        )

        # Build q query
        if device_type is None or device_type == "all":
            q = "((model:false))"
        elif device_type == "asa" or device_type == "ios":
            q = f"((model:false) AND (deviceType:{device_type.upper()})) AND (NOT deviceType:FMCE)"
        elif device_type == "ftd":
            q = (
                "((model:false) AND ((deviceType:FMC_MANAGED_DEVICE) OR (deviceType:FTDC))) AND "
                "(NOT deviceType:FMCE)"
            )
        if filter:
            q = q.replace(
                "(model:false)", f"(model:false) AND ((name:{filter}) OR (ipv4:{filter}) OR (serial:{filter}))"
            )
        # TODO: add meraki and other types...
        # Build r query
        # if device_type == None or device_type == "meraki" or device_type == "all":
        #    r = r[0:-1] + ",meraki/mxs.{status,state,physicalDevices,boundDevices,network}" + r[-1:]
        return {"q": q, "r": r}

    @staticmethod
    def get_lar_query(module_params: dict) -> str | None:
        """return a query to retrieve the SDC details"""
        filter = module_params.get("sdc")
        if filter is not None:
            return f"name:{filter} OR ipv4:{filter}"

    @staticmethod
    def get_cdfmc_query() -> str | None:
        """Return a query string to retrieve cdFMC informaton"""
        return {"q": "deviceType:FMCE"}

    @staticmethod
    def get_cdfmc_policy_query(limit: int, offset: int, access_list_name: str) -> str:
        """Return a query to retrieve the given access list name"""
        if access_list_name is not None:
            return f"name={urllib.parse.quote(access_list_name)}"
        else:
            return f"limit={limit}&offset={offset}"

    @staticmethod
    def net_obj_query(name: str = None, network: str = None, tags: list = None) -> str:
        """Return a query string for network objects given a name, network, or a list of tags"""
        q_part, q = "", ""
        if network is not None:
            q_part = f'(elements:{network.replace("/", "?")})' if "/" in network else f"(elements:{network}?32)"
        if name is not None:
            q_part = f"{q_part} AND (name:{name})" if q_part else f"(name:{name})"
        q = f"(NOT deviceType:FMCE) AND ({q_part})" if q_part else "(NOT deviceType:FMCE)"
        if tags is not None:
            tag_query = " AND ".join(f'tags.labels:"{t}"' for t in tags)
            q = f"{q} AND (({tag_query}))"
        return {"q": q}

    @staticmethod
    def pending_changes_query(module_params: dict, agg: bool = False) -> str:
        q = (
            f"device.name:{module_params.get('device_name')} AND device.configState:NOT_SYNCED AND device.model:false"
            " AND NOT device.deviceType:FTDC AND NOT device.deviceType:FMC_MANAGED_DEVICE"
        )
        r = "[targets/device-changelog.{changeLogInstance}]"
        if agg:
            return {"agg": "count", "q": q, "resolve": r}
        else:
            return {"limit": module_params.get("limit"), "offset": module_params.get("offset"), "q": q, "resolve": r}

    @staticmethod
    def pending_changes_diff_query(uid: str):
        """Given a UID of an Object Reference, generate a query to return the diff details of the config"""
        q = f"(objectReference.uid:{uid})+AND+(changeLogState:ACTIVE)"
        r = "%5Bchangelogs%2Fquery.%7Buid,lastEventTimestamp,changeLogState,events,objectReference%7D%5D"
        return {"q": q, "resolve": r, "limit": 1, "offset": 0}
