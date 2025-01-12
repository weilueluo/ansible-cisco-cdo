#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Apache License v2.0+ (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from enum import Enum


class CDOAPI(Enum):
    SVCS = "aegis/rest/v1/services"
    DEVICES = f"{SVCS}/targets/devices"
    WORKSET = f"{SVCS}/common/workingset"
    FTDS = f"{SVCS}/firepower/ftds"
    FMC = f"{SVCS}/fmc/appliance"
    OBJS = f"{SVCS}/targets/objects"
    LARS = f"{SVCS}/targets/proxies"
    ASA_CONFIG = f"{SVCS}/asa/configs"
    SPECIFIC_DEVICE = "aegis/rest/v1/device/{uid}/specific-device"
    FMC_ACCESS_POLICY = "fmc/api/fmc_config/v1/domain/{domain_uid}/policy/accesspolicies"
    DEPLOY = "aegis/rest/v1/services/targets/device-changelog"
    JOBS = "aegis/rest/v1/services/state-machines/jobs"
