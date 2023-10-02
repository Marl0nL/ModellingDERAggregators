#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Sep 19 16:50:23 2023

@author: marlon
"""

import pandas as pd
import numpy as np
import Configuration as c
import time
from pyomo.environ import *
import logging as log


def build_DSO_OPF(feeder, t, dso_inputs=c.dso_inputs):

    model = ConcreteModel()

    # Sets/Indices
    buses = feeder['buses']
    lines = feeder['lines']
    nodes = feeder['nodes']
    # time #? maybe i don't need time
    # Vars
        # Bus
    model.voltage = Var(buses.index, name='voltage', within=NonNegativeReals)
    model.P_bus_local = Var(buses.index, name='local_bus_power', within=Reals)
    model.Q_bus_local = Var(buses.index, name='local_bus_reactive', within=Reals)
        # Line
    model.current = Var(lines.index, name='current', within = Reals)
    model.P_line = Var(lines.index, name = 'line_power', within = Reals)
    model.Q_line = Var(lines.index, name = 'line_reactive', within = Reals)
        # Node
    model.import_DOE=Var(nodes.keys(), name = 'Import DOE',
                         within = NonNegativeReals)
    model.export_DOE=Var(nodes.keys(), name = 'Export DOE',
                         within = NonPositiveReals)
    # model.direction     = Var(nodes.keys(), name = 'calculation', within=Binary)
    model.P_meter=Var(nodes.keys(), name = 'P_meter', within = Reals)

    def objective_rule(m):  # Minimise curtailment.
        # C_export = 1 - m.export_DOE[n,t]/nodes[n]['export_IOE'][t]
        # C_import = 1 - m.import_DOE[n,t]/nodes[n]['export_IOE'][t]
        # return sum(C_export + C_import for n in nodes.keys())
        return sum(2
                   - m.export_DOE[n]/nodes[n]['data']['export_IOE'][t]
                   - m.import_DOE[n]/nodes[n]['data']['import_IOE'][t]
                   for n in nodes.keys()

                   )
    model.objective= Objective(rule = objective_rule, sense = minimize)

    
