#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Sep 24 21:37:44 2023

@author: marlon
"""

import Configuration as c

from pyomo.environ import *
import pao
import prepare_data as prepare
import aggregator as agg
import logging as log

def Compute_Strategic_IOEs(mx,aggregator,t,solve=True):
    
    model = ConcreteModel()
    
    nodes = aggregator['Nodes']
    xnodes = aggregator['Nodes'].copy()
    
    hindsight_horizon = 10
    
    #Vars
    model.P_import = Var(nodes.keys(),within=NonNegativeReals)
    model.P_export = Var(nodes.keys(),within=NonNegativeReals)
    model.R_bid    = Var(nodes.keys(),within=Reals)
    model.L_bid    = Var(nodes.keys(), within=Reals)
    model.upper_IOE = Var(nodes.keys(), within = Reals)
    model.lower_IOE = Var(nodes.keys(), within = Reals)

    
    model.shared_upper_capacity = Var(nodes.keys(), within = Reals)
    model.shared_lower_capacity = Var(nodes.keys(), within = Reals)
    
    model.expected_import_DOE = Var(nodes.keys(),within = Reals)
    model.expected_export_DOE = Var(nodes.keys(),within = Reals)
    
    model.import_DOE = Var(nodes.keys(), within = Reals)
    model.export_DOE = Var(nodes.keys(), within = Reals)
    
    
    def R_bid_new(m,n):
        return m.R_bid[n] <= mx.R_bid[n,t].value
    
    def L_bid_new(m,n):
        return m.L_bid[n] <= mx.L_bid[n,t].value
    
    
    def IOE_collision_rule(m,n):
        return m.lower_IOE[n] <= m.upper_IOE[n]
    
    model.ioe_collision = Constraint(nodes.keys(), rule = IOE_collision_rule)
    
    def upper_IOE_limits(m,n):
        return (nodes[n]['P_batt_min'][t]+nodes[n]['P_solar_min'][t], m.upper_IOE[n], nodes[n]['P_batt_max'][t] + nodes[n]['load_max'][t])
    
    model.upper_ioe_limits = Constraint(nodes.keys(), rule = upper_IOE_limits)
    
    
    def lower_IOE_limits(m,n):
        return (nodes[n]['P_batt_min'][t]+nodes[n]['P_solar_min'][t], m.lower_IOE[n], nodes[n]['P_batt_max'][t] + nodes[n]['load_max'][t])

    model.lower_ioe_limits = Constraint(nodes.keys(), rule = lower_IOE_limits)
    
    
    def Import_Mirror_Limitation(m, n):
        l_cap = 2*(mx.P_meter[n,t].value+mx.L_bid[n,t].value)
        
        return l_cap * m.expected_constraint[n]
    
    #model.mirror_constraint = Constraint(nodes.keys(), rule = Import_Mirror_Limitation)
    
    def Expected_iDOE_Rule(m, n):
        return m.expected_import_DOE[n] == np.mean(nodes[n]['import_DOE'][t-(1+hindsight_horizon):t-1])
        
    def Expected_eDOE_Rule(m, n):
        return m.expected_export_DOE[n] == np.mean(nodes[n]['export_DOE'][t-(1+highsight_horizon):t-1])
    
    ##### Nested DSO Problem ########   
    
    
    model.dso = pao.pyomo.SubModel(fixed=[model.upper_IOE,model.lower_IOE])
    
    
    def dso_objective_rule(model):
        mo = model.model()
        # Minimise curtailment.
        return sum((mo.upper_IOE[n] - mo.import_DOE[n] + mo.export_DOE[n] - mo.lower_IOE[n]) for n in nodes.keys())
    
    
    model.dso.objective = Objective(rule=dso_objective_rule, sense = minimize)
    
    def DOE_relative_limit(m, n):
        mo = m.model()
        return mo.import_DOE[n] >= mo.export_DOE[n]
    
    model.dso.DOE_collision = Constraint(nodes.keys(), rule = DOE_relative_limit)
    
    def import_DOE_IOE(m,n):
        mo = m.model()
        return mo.import_DOE[n] <= mo.upper_IOE[n]
    
    model.dso.imp_doe_IOE_limit = Constraint(nodes.keys(),rule = import_DOE_IOE)
    
    def import_DOE_bounds(m, n):
        mo = m.model()
        return (nodes[n]['P_solar_min'][t]+nodes[n]['P_batt_min'][t], mo.import_DOE[n], nodes[n]['load_max'][t] + nodes[n]['P_batt_max'][t])

    model.dso.import_DOE_boundaries = Constraint(
        nodes.keys(), rule = import_DOE_bounds)

    def export_DOE_IOE(m,n):
        mo = m.model()
        return mo.lower_IOE[n] <= mo.export_DOE[n]
    
    model.dso.exp_doe_IOE_limit = Constraint(nodes.keys(), rule = export_DOE_IOE)
    
    
    def export_DOE_bounds(m, n):
        mo = m.model()
        return (nodes[n]['P_batt_min'][t] + nodes[n]['P_solar_min'][t], mo.export_DOE[n], nodes[n]['P_batt_max'][t] + nodes[n]['load_max'][t])

    model.dso.export_DOE_boundaries=Constraint(
        nodes.keys(), rule = export_DOE_bounds)

    
    def network_capacity_objective(model):
        mo = model.model()
        network_capacity = sum(mo.import_DOE[n] - mo.export_DOE[n] for n in nodes.keys())
        
        return -1*network_capacity 
    
    #model.objective2 = Objective(rule=network_capacity_objective, sense = minimize)
    
    def fcas_revenue_objective(model):
        mo = model.model()
        fcas_rev = sum((mo.R_bid[n]*nodes[n]['raise_price'][t] + mo.L_bid[n]*nodes[n]['lower_price'][t])*c.interval_duration for n in nodes.keys())
        return -1*fcas_rev
    
    model.objective3 = Objective(rule=network_capacity_objective, sense = minimize)
        
    def R_bid_DOE_limit(m, n):
        return m.R_bid[n] <= mx.P_meter[n,t].value - m.export_DOE[n]
    
    model.rbid_limit = Constraint(nodes.keys(),rule = R_bid_DOE_limit)
    
    def L_bid_DOE_limit(m, n):
        return m.L_bid[n] <= mx.P_meter[n,t].value + m.import_DOE[n]
    
    model.lbid_limit = Constraint(nodes.keys(), rule = L_bid_DOE_limit)
    
    def limit_total_network_capacity(m, n):
        return (m.import_DOE[n] - m.export_DOE[n]) <= 0.9*(nodes[n]['P_batt_max'][t] + nodes[n]['load_max'][t] - (nodes[n]['P_batt_min'][t] + nodes[n]['P_solar_min'][t]))
    
    model.total_capacity_limit = Constraint(nodes.keys(), rule = limit_total_network_capacity)                                                   
    
    if solve:
        solver = pao.Solver("pao.pyomo.FA", mip_solver ='cplex_direct')
        r = solver.solve(model)
        
        if r.solver.termination_condition.__str__() != 'TerminationCondition.optimal':
            log.info('Something wrong with PAO solve. Here is the results object:')
            print(r)
            
        for node in nodes.keys():
            aggregator['Nodes'][node]['upper_IOE'][t] = model.upper_IOE[node].value
            aggregator['Nodes'][node]['lower_IOE'][t] = model.lower_IOE[node].value
        
        log.info('Completed Strategic IOE Calculation.')
    else:
        return model
        
if __name__ == "__main__":
    
    if not c.feeder['is_built']:
         prepare.initiate_loads()
         prepare.initiate_aggregators()
         c.feeder = prepare.initiate_feeder(c.aggregators)
    
    t = c.t_start
    agg_solver = c.AggregatorSolver()
    dso_solver = c.DSOSolver()
    model = agg.Aggregator_Model(c.aggregators[0], t, mode='prediction')
    r = agg_solver.solve(model)        
    if r['Solver']()['Termination condition'] != 'optimal':
        print(r)
        raise AssertionError('Aggregator Solve Failure')
    #agg.Write_Prediction_Data(c.aggregators[0], model, t,IOEs='inactive')
    
    ioemodel = Compute_Strategic_IOEs(model,c.aggregators[0],t,solve=False)
    
    solver = pao.Solver("pao.pyomo.FA", mip_solver='cplex_direct')
    r = solver.solve(ioemodel)