#!/usr/bin/env python

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import yaml
import json
import shutil

import ansible.constants as C
from ansible.executor.task_queue_manager import TaskQueueManager
from ansible.module_utils.common.collections import ImmutableDict
from ansible.inventory.manager import InventoryManager
from ansible.parsing.dataloader import DataLoader
from ansible.playbook.play import Play
from ansible.plugins.callback import CallbackBase
from ansible.vars.manager import VariableManager
from ansible import context

class ResultsCollectorJSONCallback(CallbackBase):

    def __init__(self, *args, **kwargs):
        super(ResultsCollectorJSONCallback, self).__init__(*args, **kwargs)
        self.host_ok = {}
        self.host_unreachable = {}
        self.host_failed = {}

    def v2_runner_on_unreachable(self, result):
        host = result._host
        self.host_unreachable[host.get_name()] = result

    def v2_runner_on_ok(self, result, *args, **kwargs):
        host = result._host
        self.host_ok[host.get_name()] = result
        print(json.dumps({host.name: result._result}, indent=4))

    def v2_runner_on_failed(self, result, *args, **kwargs):
        host = result._host
        self.host_failed[host.get_name()] = result


def main():
    host_list = ['192.168.164.12']
    context.CLIARGS = ImmutableDict(connection='smart', private_key_file="~/.ssh/id_rsa", forks=10, become=None,
                                    become_method=None, become_user=None, check=False, diff=False, verbosity=0)
    sources = ','.join(host_list)
    if len(host_list) == 1:
        sources += ','

    loader = DataLoader()

    results_callback = ResultsCollectorJSONCallback()

    inventory = InventoryManager(loader=loader, sources=sources)

    variable_manager = VariableManager(loader=loader, inventory=inventory)

    passwords = dict(vault_pass='')
    tqm = TaskQueueManager(
        inventory=inventory,
        variable_manager=variable_manager,
        loader=loader,
        passwords=passwords,
        stdout_callback=results_callback,
    )

    play_sources = []
    with open('/etc/ansible/mysql_install/mysql.yml') as f:
        data = yaml.load(f, yaml.SafeLoader)
        if isinstance(data, list):
            play_sources.extend(data)
        else:
            play_sources.append(data)

    for play_book in play_sources:
        play_book['hosts'] = host_list
        play_book['vars']['mysql_port'] = 33066
        # play_book['vars']['mysql_schema'] = instance.schema.name
        print("playbook", play_book)
        play = Play().load(play_book, variable_manager=variable_manager, loader=loader)

    try:
        result = tqm.run(play)
    finally:
        print("tqm has finished")
        tqm.cleanup()
        if loader:
            loader.cleanup_all_tmp_files()

    shutil.rmtree(C.DEFAULT_LOCAL_TMP, True)


if __name__ == '__main__':
    main()

