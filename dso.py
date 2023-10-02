#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Sep 10 15:23:29 2023

@author: marlon
"""
import pandas as pd
import numpy as np
import Configuration as c
import time
import utils as u
from pyomo.environ import *
import logging as log
import networkx as nx


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
    model.current = Var(lines.index, name='current', within = NonNegativeReals)
    model.P_line = Var(lines.index, name = 'line_power', within = Reals)
    model.Q_line = Var(lines.index, name = 'line_reactive', within = Reals)
        # Node
    model.import_DOE=Var(nodes.keys(), name = 'Import DOE',
                         within = Reals)
    model.export_DOE=Var(nodes.keys(), name = 'Export DOE',
                         within = Reals)
    # model.direction     = Var(nodes.keys(), name = 'calculation', within=Binary)
    model.P_meter=Var(nodes.keys(), name = 'P_meter', within = Reals)

    def objective_rule(model):  # Minimise curtailment.
        # C_export = 1 - m.export_DOE[n,t]/nodes[n]['export_IOE'][t]
        # C_import = 1 - m.import_DOE[n,t]/nodes[n]['export_IOE'][t]
        # return sum(C_export + C_import for n in nodes.keys())
        return sum((nodes[n]['data']['upper_IOE'][t] - model.import_DOE[n] + model.export_DOE[n] - nodes[n]['data']['lower_IOE'][t])**2 / (nodes[n]['data']['upper_IOE'][t] - nodes[n]['data']['lower_IOE'][t])
                   for n in nodes.keys()
                   )
    
    model.objective= Objective(rule = objective_rule, sense = minimize)

    # bus-indexed rules
    def voltage_bounds(m, b):
        return (dso_inputs['V_min']**2, m.voltage[b], dso_inputs['V_max']**2)

    model.voltage_limits=Constraint(buses.index, rule = voltage_bounds)
    

    # def bus_power_balance(m, b):
    #     lines_outbound_indexes=feeder['lookup_lines'][b]['from']
    #     lines_inbound_indexes=feeder['lookup_lines'][b]['to']
    #     node_indexes=feeder['lookup_nodes'][b]
    #     load_indexes=feeder['lookup_loads'][b]

    #     return m.P_bus[b] == (
    #         sum(m.P_line[x] for x in lines_outbound_indexes)
    #         + sum(feeder['loads'][x]['data']['P_load'][t] for x in load_indexes)
    #         + sum(m.P_meter[i] for i in nc_u_line_voltage(0)_ode_indexes)
    #         - sum(m.P_line[y] for y in lines_inbound_indexes))

    # model.bus_power_equilibrium=Constraint(
    #     buses.index, rule = bus_power_balance)
    
    
    def bus_power(m,b):
        load_indexes=feeder['lookup_loads'][b]
        node_indexes=feeder['lookup_nodes'][b]
        return m.P_bus_local[b] == sum(feeder['loads'][x]['data']['P_load'][t]*1000 for x in load_indexes) + sum(m.P_meter[i]*1000 for i in node_indexes)
    
    def bus_reactive(m,b):
        return m.Q_bus_local[b] == 0#np.random.uniform(-0.05,0.05)*m.P_bus_local[b]
    
    model.bus_p_local = Constraint(buses.index, rule=bus_power)
    model.bus_q_local = Constraint(buses.index, rule=bus_reactive)
    
    def bus_voltage(m,b):
        if b == 0: #Slack bus condition
            return m.voltage[b] == feeder['V_ref']**2
        line_in = feeder['lookup_lines'][b]['to'][0]
        a_index = lines['from_bus'][line_in]
        
        return m.voltage[b] ==  m.voltage[a_index] - 2*(lines['r'][line_in]*m.P_line[line_in] + lines['x'][line_in]*m.Q_line[line_in]) + (lines['r'][line_in]**2 + lines['x'][line_in]**2)*m.current[line_in]
    
    model.voltage_calculation = Constraint(buses.index, rule = bus_voltage, name = 'bus_volt')
    
    # Line-indexed rules
    def line_voltage_rule(m, l):
        #return m.current[l]*m.voltage[lines['from_bus'][l]] >= m.P_line[l]**2 + m.Q_line[l]**2
        return -1*m.current[l]*m.voltage[lines['from_bus'][l]] + m.P_line[l]**2 + m.Q_line[l]**2 <= 0    

    model.line_voltage = Constraint(lines.index, rule=line_voltage_rule)
    #def line_reactive_rule(m, l):
        
    def line_active_rule(m, l):
        a_index = lines['from_bus'][l]
        b_index = lines['to_bus'][l]
        downstream_lines = feeder['lookup_lines'][b_index]['from'] 
        return m.P_line[l] == m.P_bus_local[b_index]/feeder['S_base'] + sum(m.P_line[x] for x in downstream_lines)
    
    
    model.line_active=Constraint(lines.index, rule = line_active_rule)

    def line_reactive_rule(m, l):
        a_index = lines['from_bus'][l]
        b_index = lines['to_bus'][l]
        downstream_lines = feeder['lookup_lines'][b_index]['from']
        return m.Q_line[l] == m.Q_bus_local[b_index] / feeder['S_base'] + sum(m.Q_line[x] for x in downstream_lines)
    
    
    model.line_reactive = Constraint(lines.index, rule = line_reactive_rule)
    
    def current_bounds(m, l):
        #return (-1*lines['max_i'][l], m.current[l], lines['max_i'][l])
        return (0, m.current[l], lines['max_i'][l]**2)
    model.current_limits= Constraint(lines.index, rule = current_bounds)
    
    
    

    # Node-indexed rules
    
    def meter_power_limits(m, a, n):
        return (nodes[(a,n)]['data']['P_solar_min'][t]+nodes[(a,n)]['data']['P_batt_min'][t], m.P_meter[(a,n)], nodes[(a,n)]['data']['P_batt_max'][t] + nodes[(a,n)]['data']['load_max'][t])

    def DOE_relative_limit(m, a, n):
        return m.import_DOE[(a,n)] >= m.export_DOE[(a,n)]
    
    model.doe_collision = Constraint(nodes.keys(), rule = DOE_relative_limit)

    def import_DOE_bounds(m, a, n):
        return (nodes[(a,n)]['data']['P_solar_min'][t]+nodes[(a,n)]['data']['P_batt_min'][t], m.import_DOE[(a,n)], nodes[(a,n)]['data']['upper_IOE'][t])

    model.import_DOE_boundaries = Constraint(
        nodes.keys(), rule = import_DOE_bounds)

    def export_DOE_bounds(m, a, n):
        return (nodes[(a,n)]['data']['lower_IOE'][t], m.export_DOE[(a,n)], nodes[(a,n)]['data']['P_batt_max'][t] + nodes[(a,n)]['data']['load_max'][t])

    model.export_DOE_boundaries=Constraint(
        nodes.keys(), rule = export_DOE_bounds)


    def DERfree_OPF_rule(m, a, n):
        return m.P_meter[(a,n)] == 0.0

    model.DERfree_OPF=Constraint(nodes.keys(), rule = DERfree_OPF_rule)

    def ImportDOE_OPF_rule(m, a, n):
        if feeder['nodes'][(a,n)]['data']['Online'][t] == 0:
            return m.P_meter[(a,n)] == nodes[(a,n)]['data']['load_max'][t]+nodes[(a,n)]['data']['P_batt_max'][t]
        return m.P_meter[(a,n)] == m.import_DOE[(a,n)]
    
    model.import_OPF = Constraint(nodes.keys(), rule = ImportDOE_OPF_rule)
    
    def ExportDOE_OPF_rule(m, a, n):
        if feeder['nodes'][(a,n)]['data']['Online'][t] == 0:
            return m.P_meter[(a,n)] == nodes[(a,n)]['data']['P_batt_min'][t] + nodes[(a,n)]['data']['P_solar_min'][t]
        return m.P_meter[(a,n)] == m.export_DOE[(a,n)]
    
    model.export_OPF = Constraint(nodes.keys(), rule = ExportDOE_OPF_rule)
    
    return model


def DOE_Step_Solve(model,solver):
    model.import_OPF.deactivate()
    model.DERfree_OPF.deactivate()
    model.export_OPF.activate()
    r1 = solver.solve(model)
    if r1['Solver']()['Termination condition'] != 'optimal':
        log.warning('Relaxing barrier quadratic convergence tolerance.')
        solver.options['set barrier qcpconvergetol 1e-05']
        r1 = solver.solve(model)
        if r1['Solver']()['Termination condition'] != 'optimal':
            raise AssertionError('R1 failed with lower convergence tolerance.')
        else:
            solver.option['set barrier qcpconvergetol 1e-06']
    for index in model.export_DOE.index_set():
        model.export_DOE[index].fix()
    
    model.import_OPF.activate()
    model.export_OPF.deactivate()
    r2 = solver.solve(model)
    if r2['Solver']()['Termination condition'] != 'optimal':
        log.warning('Relaxing barrier quadratic convergence tolerance.')
        solver.options['set barrier qcpconvergetol 1e-05']
        r2 = solver.solve(model)
        if r2['Solver']()['Termination condition'] != 'optimal':
            raise AssertionError('R2 failed with lower convergence tolerance.')
        else:
            solver.option['set barrier qcpconvergetol 1e-06']
    for index in model.import_DOE.index_set():
        model.import_DOE[index].fix()
        
    return model

def Write_DOEs(model,t,feeder):
    for node in feeder['nodes'].keys():
        feeder['nodes'][node]['data']['import_DOE'][t] = model.import_DOE[node].value
        feeder['nodes'][node]['data']['export_DOE'][t] = model.export_DOE[node].value

def Fix_Actual_Powers(model,t,feeder):
    model.import_OPF.deactivate()
    model.export_OPF.deactivate()
    for index in model.P_meter.index_set():
        model.P_meter[index].fix(feeder['nodes'][index]['data']['P_meter'][t])
    
    

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
    
    model = build_DSO_OPF(c.feeder,c.t_start-1)
    
    solver = SolverFactory('cplex', executable = c.cplex_path)
    memstring = 'set workmem '+str(c.RAM)
    solver.options[memstring]
    if c.set_memory_emphasis:
        solver.options['set emphasis memory 1']
        
    # Run 1 - network state without controlled DER.
    model.import_OPF.deactivate()
    model.export_OPF.deactivate()
    #model.write('dsotest.lp',format='cpxlp')
    result = solver.solve(model,tee=True,symbolic_solver_labels=True)
    
    if result['Solver']()['Termination condition'] == 'infeasible':
        result.pprint()
        log.info('Non-prosumer solve has failed.')
        exit(99)
    
    # Run 2 - import DOE calculation
    model.DERfree_OPF.deactivate()
    model.import_OPF.activate()
    
    
    solver.solve(model,warmstart=True,tee=True)

    result = solver.solve(model,symbolic_solver_labels=True)
    if result['Solver']()['Termination condition'] == 'infeasible':
        log.info('Import DOE calculation solve has failed.')
        exit(99)
    
    # Run 3 - export DOE calculation
    
    for index in model.import_DOE.index_set():
        model.import_DOE[index].fix()
    
    voltages = []
    for b in buses.index:
        voltages += [model.voltage[b].value]
    
    
    model.import_OPF.deactivate()
    model.export_OPF.activate()
    
    
    solver.solve(model,warmstart=True)
    

    
    print('Test complete.')
    u.write_lp(model,'working_dso.lp')
    #voltages = []
    #for b in buses.index:
    #    voltages += [model.voltage[b].value]
    voltages = []
    for b in buses.index:
        voltages += [model.voltage[b].value]
        
    constrained_lines = [x for x in lines.index if lines['max_i'][x]-0.1 <= model.current[x].value]
    
    
    max_volt = np.max(voltages)
    max_bus = np.argmax(voltages)
    
    log.info(f'Max voltage of {max_volt} seen at bus {max_bus}.')
    
    constrained_nodes = feeder['lookup_nodes'][max_bus]
    print(f'Nodes at constrained bus: \n {constrained_nodes}')
    score = []
    for node in feeder['nodes'].keys():
        score += [1-(model.export_DOE[node].value/(feeder['nodes'][node]['data']['P_batt_min'][0]+feeder['nodes'][node]['data']['P_solar_min'][0]))]
    

    
    G = nx.from_pandas_edgelist(lines, source='from_bus',target = 'to_bus', edge_attr='max_i')
    nx.draw_networkx(G)