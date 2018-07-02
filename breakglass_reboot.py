#!/usr/bin/env python

from __future__ import print_function
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim
from tools import tasks
from pprint import pprint

import atexit
import argparse
import getpass
import ssl

def GetArgs():
    parser = argparse.ArgumentParser(description='Process args for machine reboot')

    parser.add_argument('-s', '--host', required=True, action='store', help='Remote host to connect to')
    parser.add_argument('-o', '--port', type=int, default=443, action='store', help='Port to connect on')
    parser.add_argument('-u', '--user', required=True, action='store', help='User name to use when connecting to host')
    parser.add_argument('-p', '--password', required=False, action='store', help='Password to use when connecting to host')
    parser.add_argument('-d', '--disks', default=None, action='store', help='Disk array to target for VM reboots')

    args = parser.parse_args()
    return args

def DISCOVER(C):
    UUIDs = []
    MAX_DEPTH = 10

    def _FINDUUID(item, depth=1):
        if hasattr(item, 'childEntity'):
            if depth > MAX_DEPTH:
                return
            for child in item.childEntity:
                _FINDUUID(child, depth+1)
            return
        UUIDs.append(item.summary.config.uuid)

    for c in C.rootFolder.childEntity:
        for this in c.vmFolder.childEntity:
            _FINDUUID(this)
    return UUIDs

def DISKHUNT(C, V):
    NOTFOUND = []
    VMBYDISK = {}
    for vm in V:
        machine = C.content.searchIndex.FindByUuid(None, vm, True)
        if machine is None:
            print("{0} was not found".format(vm))
            NOTFOUND.append(vm)
        else:
            dstores = machine.datastore
            for d in dstores:
                if d.name in VMBYDISK:
                    VMBYDISK[d.name].append(machine)
                else:
                    VMBYDISK[d.name] = [machine]

    return NOTFOUND, VMBYDISK

def main():
    ARGS = GetArgs()
    CONN = None

    if ARGS.password:
        P = ARGS.password
    else:
        P = getpass.getpass(prompt='Password: ')

    if hasattr(ssl, '_create_unverified_context'):
        context = ssl._create_unverified_context()
    else:
        context = None

    try:
        CONN = SmartConnect(host=ARGS.host, user=ARGS.user, pwd=P, port=ARGS.port, sslContext=context)
        atexit.register(Disconnect, CONN)
    except IOError as ex:
        raise SystemExit("Failed connection to {0}:{1}".format(ARGS.host, ARGS.port))
    except vim.fault.InvalidLogin:
        raise SystemExit("{0} login failure".format(ARGS.user))

    CONTENTS = CONN.RetrieveContent()
    VMs = DISCOVER(CONTENTS)
    VMs = sorted(set(VMs))

    NOTFOUND, VMBYDISK = DISKHUNT(CONN, VMs)

    if ARGS.disks is None:
        print('Discovered datastores: ')
        for datastore, vm in VMBYDISK.iteritems():
            print('{0} contains:'.format(datastore))
            for v in vm:
                print(v.name)
            print()
    elif ARGS.disks in VMBYDISK:
        print(ARGS.disks)
        for v in VMBYDISK[ARGS.disks]:
            print("rebooting {0}".format(v.name))
            # print("{0} status: {1}".format(v.name, v.runtime.powerState))
            STATUS = str(v.runtime.powerState)
            if STATUS == 'poweredOn':
                TASK = v.ResetVM_Task()
                tasks.wait_for_tasks(CONN, [TASK])
    else:
        print('{0} was not found!'.format(ARGS.disks))
        print('Available datastores:')
        for datastore in VMBYDISK:
            print(datastore)

if __name__ == "__main__":
    main()
