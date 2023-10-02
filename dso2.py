#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Sep 17 21:34:54 2023

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
    
    # Vars
        # Bus
    model.voltage = Var(buses.index, name='voltage', within=NonNegativeReals, initialize=1)
    model.P_bus_local = Var(buses.index, name='local_bus_power', within=Reals)
    model.Q_bus_local = Var(buses.index, name='local_bus_reactive', within=Reals)
        # Line
    model.current = Var(lines.index, name='current', within = Reals, initialize=0)
    model.P_line = Var(lines.index, name = 'line_power', within = Reals)
    model.Q_line = Var(lines.index, name = 'line_reactive', within = Reals)
        # Node
    model.import_DOE=Var(nodes.keys(), name = 'Import DOE',
                         within = NonNegativeReals)
    model.export_DOE=Var(nodes.keys(), name = 'Export DOE',
                         within = NonPositiveReals)
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
    
    # bus-indexed rules
    def voltage_bounds(m, b):
        if b == 0:
            return m.voltage[b] == 1.0
        return (dso_inputs['V_min'], m.voltage[b], dso_inputs['V_max'])

    model.voltage_limits=Constraint(buses.index, rule = voltage_bounds, name = 'voltage bounds')
    
    def bus_power(m,b):
        load_indexes=feeder['lookup_loads'][b]
        node_indexes=feeder['lookup_nodes'][b]
        return m.P_bus_local[b] == sum(feeder['loads'][x]['data']['P_load'][t] for x in load_indexes) + sum(m.P_meter[i] for i in node_indexes)
    
    
    def bus_reactive(m,b):
        return m.Q_bus_local[b] == 0.0
    
    model.bus_p_local = Constraint(buses.index, rule=bus_power, name='busPlocal')
    model.bus_q_local = Constraint(buses.index, rule=bus_reactive, name = 'busQlocal')
    
    def bus_voltage(m,b):
        if b == 0: #Slack bus condition
            return m.voltage[b] == feeder['V_base']
        line_in = feeder['lookup_lines'][b]['to'][0]
        a_index = lines['from_bus'][line_in]
        
        return m.voltage[b] ==  m.voltage[a_index] - 2*(lines['r'][line_in]*m.P_line[line_in] + lines['x'][line_in]*m.Q_line[line_in]) + (lines['r'][line_in]**2 + lines['x'][line_in]**2)*m.current[line_in]
    
    
    model.bus_voltage_constraint = Constraint(buses.index, rule = bus_voltage, name = 'bus_voltage')
    
    def line_active_rule(m, l):
        a_index = lines['from_bus'][l]
        b_index = lines['to_bus'][l]
        downstream_lines = feeder['lookup_lines'][b_index]['from']
        if len(downstream_lines) == 0:
            return m.P_line[l] == m.P_bus_local[b_index]/feeder['S_base']
        return m.P_line[l] == m.P_bus_local[b_index]/feeder['S_base'] + sum(m.P_line[x] for x in downstream_lines)
    
    
    model.line_active=Constraint(lines.index, rule = line_active_rule, name = 'line_active_power')
    
    def line_reactive_rule(m, l):
        a_index = lines['from_bus'][l]
        b_index = lines['to_bus'][l]
        downstream_lines = feeder['lookup_lines'][b_index]['from']
        return m.Q_line[l] == m.Q_bus_local[b_index] + sum(m.Q_line[x] for x in downstream_lines)
    
    
    model.line_reactive = Constraint(lines.index, rule = line_reactive_rule, name = 'f23fs', doc = 'abc')
    
    def current_bounds(m, l):
        return (-1*lines['max_i'][l], m.current[l], lines['max_i'][l])
    
    model.current_limits= Constraint(lines.index, rule = current_bounds, name = 'current_bounds', doc = 'xyz')
    
    def meter_power_limits(m, a, n):
        return (nodes[(a,n)]['data']['P_solar_min'][t]+nodes[(a,n)]['data']['P_batt_min'][t], m.P_meter[(a,n)], nodes[(a,n)]['data']['P_batt_max'][t] + nodes[(a,n)]['data']['load_max'])

    def import_DOE_bounds(m, a, n):
        return (0, m.import_DOE[(a,n)], nodes[(a,n)]['data']['load_max'][t]+nodes[(a,n)]['data']['P_batt_max'][t])

    model.import_DOE_boundaries = Constraint(
        nodes.keys(), rule = import_DOE_bounds)

    def export_DOE_bounds(m, a, n):
        return (nodes[(a,n)]['data']['P_batt_min'][t] + nodes[(a,n)]['data']['P_solar_min'][t], m.export_DOE[(a,n)], 0)

    model.export_DOE_boundaries=Constraint(
        nodes.keys(), rule = export_DOE_bounds)


    def DERfree_OPF_rule(m, a, n):
        return m.P_meter[(a,n)] == 0.0

    model.DERfree_OPF=Constraint(nodes.keys(), rule = DERfree_OPF_rule)

    def ImportDOE_OPF_rule(m, a, n):
        return m.P_meter[(a,n)] == m.import_DOE[(a,n)]
    
    model.import_OPF = Constraint(nodes.keys(), rule = ImportDOE_OPF_rule)
    
    def ExportDOE_OPF_rule(m, a, n):
        return m.P_meter[(a,n)] == m.export_DOE[(a,n)]
    
    model.export_OPF = Constraint(nodes.keys(), rule = ExportDOE_OPF_rule)
    
    

    return model

if __name__ == "__main__":
    import prepare_data as prep
    print('Running test of DSO OPF model.')
    if not c.feeder['is_built']:
        prep.initiate_loads()
        prep.initiate_aggregators()
        c.feeder = prep.initiate_feeder(c.aggregators)
    
    feeder = c.feeder
    lines = feeder['lines']
    buses = feeder['buses']
    from pyomo.util import infeasible
    model = build_DSO_OPF(c.feeder,0)
    
    solver = SolverFactory('cplex', executable = c.cplex_path)
    memstring = 'set workmem '+str(c.RAM)
    solver.options[memstring]
    if c.set_memory_emphasis:
        solver.options['set emphasis memory 1']
        
    # Run 1 - network state without controlled DER.
    model.import_OPF.deactivate()
    model.export_OPF.deactivate()
    model.write('dsotest.lp',format='cpxlp')
    result = solver.solve(model,tee=True,symbolic_solver_labels=True)
    
    if result['Solver']()['Termination condition'] == 'infeasible':
        log.info('Non-prosumer solve has failed.')
        exit(99)
    
    # Run 2 - import DOE calculation
    model.DERfree_OPF.deactivate()
    #model.import_OPF.activate()
    
    
    #solver.solve(model,warmstart=True)

    result = solver.solve(model,symbolic_solver_labels=True)
    if result['Solver']()['Termination condition'] == 'infeasible':
        log.info('Import DOE calculation solve has failed.')
        exit(99)
    
    # Run 3 - export DOE calculation
    
    #for index in model.import_DOE.index_set():
    #    model.import_DOE[index].fix()
        
    model.import_OPF.deactivate()
    model.export_OPF.activate()
    
    #solver.solve(model,warmstart=True)
    
    
    
    print('Test complete.')