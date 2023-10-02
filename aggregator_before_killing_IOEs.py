#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Aug 26 20:52:34 2023

@author: marlon
"""

from pyomo.environ import *
import Configuration as conf
import pandas as pd
#import math
import numpy as np
import logging as log

def Aggregator_Model(aggregator,t,mode='prediction',horizon=conf.horizon_intervals,IOEs='inactive'):
    #Indices
    nodes = aggregator['Nodes']
    T = list(range(int(t),int(t+horizon)))
    model = ConcreteModel()
            

    #Variables
    #General
    model.P_meter =     Var(nodes.keys(),T,name = 'P_meter',within=Reals)
    model.P_solar =     Var(nodes.keys(),T,name = 'P_solar',within=NonPositiveReals)
    model.P_batt =      Var(nodes.keys(),T,name = 'P_batt',within=Reals)

    model.SOC =         Var(nodes.keys(),T,name = 'SOC',within=NonNegativeReals)
    model.Online =      Var(nodes.keys(),T,name = 'Online',within=Binary)
    model.P_import =    Var(nodes.keys(),T,name = 'Import',within=NonNegativeReals)
    model.P_export =    Var(nodes.keys(),T,name = 'Export',within=NonNegativeReals)
    model.sign =        Var(nodes.keys(), T, name = 'Import/Export Sign', within=Boolean)
    model.P_batt_sign = Var(nodes.keys(),T,name = 'P_batt_sign',within=Binary)
    model.P_batt_charge = Var(nodes.keys(), T, name = 'P_batt_charge',within=NonNegativeReals)
    model.P_batt_discharge = Var(nodes.keys(), T, name = 'P_batt_discharge', within=NonNegativeReals)
    #FCAS, per site per interval
    model.R_bid =       Var(nodes.keys(),T,name = 'raise_price',within=Reals)
    model.L_bid =       Var(nodes.keys(),T,name = 'lower_price',within=Reals)
    model.R_batt =      Var(nodes.keys(),T,name = 'battery_raise',within=NonNegativeReals)
    model.L_batt =      Var(nodes.keys(),T,name = 'battery_lower',within=NonNegativeReals)
    model.L_solar =     Var(nodes.keys(),T,name = 'solar_lower',within=NonNegativeReals)
    
    #FCAS, aggregate per interval
    model.R_bid_agg =   Var(T,name = 'R_bid_aggregate',within=NonNegativeReals)
    #model.R_bid_fleet = Var(T,name = 'Total_Raise_Bid',within=NonNegativeIntegers)
    #model.R_bid_frac =  Var(T,name = 'Raise_Fraction_Part',within=NonNegativeReals)
    model.L_bid_agg =   Var(T,name = 'L_bid_aggregate',within=NonNegativeReals)
    #model.L_bid_fleet = Var(T,name = 'Total_Lower_Bid',within=NonNegativeIntegers)
    #model.L_bid_frac =  Var(T,name = 'Lower_Fraction_Part',within=NonNegativeReals)
    
    #IOEs
    #model.import_IOE =  Var(nodes.keys(),T,name = 'Import IOE',within=NonNegativeReals)
    #model.export_IOE =  Var(nodes.keys(),T,name = 'Export IOE',within=NonPositiveReals) 
    
    model.import_doe_breach = Var(nodes.keys(),T,name = 'DOE Breached',within=Binary)
    model.export_doe_breach = Var(nodes.keys(),T,name = 'DOE Breached',within=Binary)
     
# Objective
    def objective_rule(model):
        #Tariff
       

        tariff_cost = sum(
            (   # no unit             kW                         h                 $/kWh
                (model.P_import[n, t]*conf.interval_duration) * nodes[n]['import_price'][t] -
                (model.P_export[n, t]*conf.interval_duration) * nodes[n]['export_price'][t]
                for n in nodes.keys()
                for t in T
            )
        )
        
        #FCAS
        #Note: currently not designed to handle per-site FCAS pricing, even though `node` structure would suggest it's doable.
        #Also worth noting that the commented-out line is the proper calculation but it takes too long to run.
        FCAS_revenue = sum(
            #       MW                   h                  convert to $/MWh from $/kW*h
            (model.R_bid_agg[t]*conf.interval_duration) * 1000*nodes[0]['raise_price'][t] + (model.L_bid_agg[t] * 1000*conf.interval_duration) * nodes[0]['lower_price'][t]
            #(model.R_bid_fleet[t]*conf.interval_duration) * 1000*nodes[0]['raise_price'][t] + (model.L_bid_fleet[t] * 1000*conf.interval_duration) * nodes[0]['lower_price'][t])
            for t in T
        )
        
        import_DOE_Breach_Penalty = sum(100*model.P_import[n,t]*conf.interval_duration*model.import_doe_breach[n, t] for n in nodes.keys() for t in T)
        export_DOE_Breach_Penalty = sum(100*model.P_export[n,t]*conf.interval_duration*model.export_doe_breach[n, t] for n in nodes.keys() for t in T)
        return tariff_cost - FCAS_revenue + import_DOE_Breach_Penalty + export_DOE_Breach_Penalty

    model.objective = Objective(rule=objective_rule, sense=minimize)
    
    #This objective is excellent for debugging as it simply targets 0 grid power.
    def MSC_objective_rule(model):
        import_volume = sum(model.P_import[n,t] for n in nodes.keys() for t in T)
        export_volume = sum(model.P_export[n,t] for n in nodes.keys() for t in T)
        return import_volume+export_volume
    
    #model.objective = Objective(rule=MSC_objective_rule, sense=minimize)
    
    # Constraint functions
    def initial_SOC_constraint(m,n):
        return m.SOC[n,T[0]] == nodes[n]['SOC'][(T[0]-1)]
    
    #def power_balance_rule(m,n,t):
    #    return m.P_meter[n,t] == nodes[n]['P_load'][t] + m.P_solar[n,t] + m.P_batt[n,t]
    
    def power_balance_rule(m,n,t):
        return nodes[n]['P_load'][t] + m.P_solar[n,t] + m.P_batt[n,t] - m.P_import[n,t] + m.P_export[n,t] == 0
    
    def P_meter_components_rule(m,n,t):
        return m.P_meter[n,t] == m.P_import[n,t] - m.P_export[n,t]
    
    def P_export_bounds(m,n,t):
        return (0, m.P_export[n,t], 1000)

    def P_import_bounds(m,n,t):
        return (0, m.P_import[n,t], 1000)
    
    def P_export_sign_rule(m,n,t):
        return m.P_export[n,t] <= 1000*(1-m.sign[n,t])
    
    def P_import_sign_rule(m,n,t):
        return m.P_import[n,t] <= 1000*m.sign[n,t]
    
    # def DOE_rule(m,n,t): #(lower bound, expr, upper bound) construction
    #     return (
    #         nodes[n]['export_DOE'][t]+((1-m.Online[n,t])*(nodes[n]['P_solar_min'][t]+nodes[n]['P_batt_min'][t])),
    #         m.P_meter[n,t],
    #         nodes[n]['import_DOE'][t]+((1-m.Online[n,t])*(nodes[n]['P_load_max'][t]+nodes[n]['P_batt_max'][t]))
    #             )

    # def DOE_rule(m,n,t): #(lower bound, expr, upper bound) construction
    #     return (
    #         nodes[n]['export_DOE'][t]+((nodes[n]['P_solar_min'][t]+nodes[n]['P_batt_min'][t])),
    #         m.P_meter[n,t],P_import[n,t] - nodes[n]['import_DOE']
    #         nodes[n]['import_DOE'][t]+((nodes[n]['P_load_max'][t]+nodes[n]['P_batt_max'][t]))
    #             )
    
    def Battery_P_limits(m,n,t):
        return (nodes[n]['P_batt_min'][t], m.P_batt[n,t], nodes[n]['P_batt_max'][t])
    
    def Solar_P_limits(m,n,t):
        return (nodes[n]['solar'][t], m.P_solar[n,t], nodes[n]['P_solar_max'][t])
    
    def delta_SOC_relationship(m,n,t):
        if t == T[-1]:
            return m.SOC[n,t] == m.SOC[n,(t-1)] + (m.P_batt_charge[n,t] * nodes[n]['battery_eta'][t]+m.P_batt_discharge[n,t]/nodes[n]['battery_eta'][t]) * conf.interval_duration
        return m.SOC[n,(t+1)] == m.SOC[n,t] + (m.P_batt_charge[n,t] * nodes[n]['battery_eta'][t] - m.P_batt_discharge[n,t]/nodes[n]['battery_eta'][t]) * conf.interval_duration
    
    def P_batt_rule(m,n,t):
        return m.P_batt[n,t] == m.P_batt_charge[n,t] - m.P_batt_discharge[n,t]
    
    def P_batt_sign_rule1(m,n,t):
        return m.P_batt_charge[n,t] <= 1000*(m.P_batt_sign[n,t])
    
    def P_batt_sign_rule2(m,n,t):
        return m.P_batt_discharge[n,t] <= 1000*(1-m.P_batt_sign[n,t])

    def P_batt_charge_limit(m,n,t):
        return (0, m.P_batt_charge[n,t], nodes[n]['P_batt_max'][t])
    
    def P_batt_discharge_limit(m,n,t):
        return (0, m.P_batt_charge[n,t], -1*nodes[n]['P_batt_min'][t])
    
    model.charge_limit = Constraint(nodes.keys(),T, rule = P_batt_charge_limit)
    model.discharge_limit = Constraint(nodes.keys(),T,rule = P_batt_discharge_limit)
    model.p_batt_decomposition = Constraint(nodes.keys(),T, rule = P_batt_rule)
    model.P_batt_sign1 = Constraint(nodes.keys(), T, rule = P_batt_sign_rule1)
    model.P_batt_sign2 = Constraint(nodes.keys(), T, rule = P_batt_sign_rule2)
    
    
    
    def P_batt_energy_rule1(m,n,t):
        return (nodes[n]['SOC_min'][t] - m.SOC[n,t])/conf.interval_duration <= m.P_batt[n,t]
    
    def P_batt_energy_rule2(m,n,t):
        return m.P_batt[n,t] <= (nodes[n]['SOC_max'][t] - m.SOC[n,t])/conf.interval_duration
    # def available_energy_constraint(m,n,t):
    #     if t == T[-1]:
    #         return ((m.SOC[n,t] - nodes[n]['SOC_min'][t]), m.SOC[n, t], (nodes[n]['SOC_max'][t] - m.SOC[n,t]))
    #     return ((m.SOC[n,t] - nodes[n]['SOC_min'][t]), m.SOC[n, (t+1)], (nodes[n]['SOC_max'][t] - m.SOC[n,t])) 
        
    def SOC_limits(m,n,t):
        if t == T[-1]:
            return (nodes[n]['SOC_min'][t], m.SOC[n,t], nodes[n]['SOC_max'][t])
        return (nodes[n]['SOC_min'][t], m.SOC[n,(t+1)], nodes[n]['SOC_max'][t])
   
    #FCAS Constraint Functions
    def R_bid_frac_bounds(m,t):
        return (0, m.R_bid_frac[t], 1)
    
    def L_bid_frac_bounds(m,t):
        return (0, m.L_bid_frac[t], 1)
    
    def Agg_L_fraction_rule(m,t):
        return m.L_bid_fleet[t]+m.L_bid_frac[t] == m.L_bid_agg[t]
        
    def Aggregate_L_bids(m,t): #MW
        return m.L_bid_agg[t] == sum(m.L_bid[n,t] for n in nodes.keys())/1000
    
    def Agg_R_fraction_rule(m,t):
        return m.R_bid_fleet[t]+m.R_bid_frac[t] == m.R_bid_agg[t]
        
    def Aggregate_R_bids(m,t):
                    #MW             kW
        return m.R_bid_agg[t] == sum(m.R_bid[n,t] for n in nodes.keys())/1000
    
    def R_battery_bounds(m,n,t):
        return (0.0, m.R_batt[n,t], nodes[n]['P_batt_max'][t] - nodes[n]['P_batt_min'][t])
    
    def R_battery_P_rule(m,n,t):
        return m.R_batt[n,t] <= m.P_batt[n,t] - nodes[n]['P_batt_min'][t]
    
    def R_battery_energy(m,n,t):
        return m.P_batt[n,t] - m.R_batt[n,t] <= (m.SOC[n,t] - nodes[n]['SOC_min'][t]) / (nodes[n]['battery_eta'][t] * conf.interval_duration)
    
    def R_DOE_compliance(m,n,t):
        return m.P_meter[n,t] - m.R_bid[n,t] >= nodes[n]['export_DOE'][t]
    
    def R_bid_constraint(m,n,t):
        return m.R_bid[n,t] <= m.R_batt[n,t]
    
    def L_battery_bounds(m,n,t):
        return (0, m.L_batt[n,t], nodes[n]['P_batt_max'][t] - nodes[n]['P_batt_min'][t])
    
    def L_battery_P_rule(m,n,t):
        return m.L_batt[n,t] <= nodes[n]['P_batt_max'][t] - m.P_batt[n,t] 
    
    def L_battery_energy(m,n,t):
        return m.P_batt[n,t] +  m.L_batt[n,t] <= (nodes[n]['SOC_max'][t] - m.SOC[n,t]) / (nodes[n]['battery_eta'][t] * conf.interval_duration)
    #Constraint declarations
    
    def L_solar_bounds(m,n,t):
        return (0, m.L_solar[n,t], -1*nodes[n]['P_solar_min'][t])
    
    def L_solar_P_rule(m,n,t):
        return m.L_solar[n,t] <= (-1*m.P_solar[n,t])
    
    def L_DOE_compliance(m,n,t):
        return m.P_meter[n,t] + m.L_bid[n,t] <= nodes[n]['import_DOE'][t]
    
    def L_bid_constraint(m,n,t):
        return m.L_bid[n,t] <= m.L_batt[n,t] + m.L_solar[n,t]
    
    def random_online_status(m,n,t):
        psi = np.random.random()
        if psi >= aggregator['Expected Offline Fraction']:
            return m.Online[n,t] == 1
        elif psi <= aggregator['Expected Offline Fraction']:
            return m.Online[n,t] == 0
    
    def Offline_within_reason(m,t):
        return sum(m.Online[n,t] for n in nodes.keys()) >= (1-aggregator['Expected Offline Fraction'])*len(nodes.keys())
    
    def Non_Selective_Offline(m,n,t):
        return m.Online[n,t] == nodes[n]['Online'][t]
    
    #IOE constraints (not all applied at once)
    def static_import_IOE_rule(m,n,t):
        return m.import_IOE[n,t] == nodes[n]['P_batt_max'][t] + nodes[n]['load_max'][t]
    
    def static_export_IOE_rule(m,n,t):
        return m.export_IOE[n,t] == nodes[n]['P_batt_min'][t] + nodes[n]['P_solar_min'][t]
    
    def NonStrategic_Import_IOE_rule(m,n,t):
        return m.import_IOE[n,t] == quicksum([m.L_bid[n,t],m.P_meter[n,t]])
    
    def NonStrategic_Export_IOE_rule(m,n,t):
        return m.export_IOE[n,t] == quicksum([m.P_meter[n,t],-1*m.R_bid[n,t]])
    

    def Minimum_Import_IOE(m,n,t):
        return m.import_IOE[n,t] >= 0.000001
    
    def Maximum_Export_IOE(m,n,t):
        return m.export_IOE[n,t] <= -0.000001
    
    #model.min_import_IOE = Constraint(nodes.keys(),T, rule = Minimum_Import_IOE)
    #model.max_export_IOE = Constraint(nodes.keys(),T, rule = Maximum_Export_IOE)
    
    def Strategic_Import_IOE_rule(m,n,t):
        return (m.P_meter[n,t], m.import_IOE[n,t], nodes[n]['P_batt_max'][t]+nodes[n]['load_max'][t])
    
    def Strategic_Export_IOE_rule(m,n,t):
        return (nodes[n]['P_batt_min'][t]+nodes[n]['P_solar_min'][t], m.export_IOE[n,t], m.P_meter[n,t])
    
    if IOEs == 'active':
            
        if aggregator['Behaviour'] == 'Non-strategic':
            model.set_import_IOE = Constraint(nodes.keys(),T,rule=NonStrategic_Import_IOE_rule)
            model.set_export_IOE = Constraint(nodes.keys(),T,rule=NonStrategic_Export_IOE_rule)
        elif aggregator['Behaviour'] == 'Strategic':
            model.set_import_IOE = Constraint(nodes.keys(),T,rule=Strategic_Import_IOE_rule)
            model.set_export_IOE = Constraint(nodes.keys(),T,rule=Strategic_Export_IOE_rule)
        else:
            log.error("Invalid aggregator behaviour input. Must be Non-strategic or Strategic.")
            raise AssertionError('Invalid aggregator behaviour input.')
        
    elif IOEs == 'inactive':
        model.set_import_IOE = Constraint(nodes.keys(),T,rule=static_import_IOE_rule)
        model.set_export_IOE = Constraint(nodes.keys(),T,rule=static_export_IOE_rule)
    else:
        raise AssertionError('IOEs input should be set to active or inactive, not whatever you gave the function.')

    

    # def no_breach_condition(m,n,t):
    #         return m.doe_breach[n,t] == 0
        
    #model.no_breach_penalty = Constraint(nodes.keys(),T, rule=no_breach_condition)
    #basic constraints (always applicable)
    model.initial_SOC = Constraint(nodes.keys(),rule=initial_SOC_constraint)
    model.power_balance = Constraint(nodes.keys(),T, rule=power_balance_rule)
    model.battery_P_limits = Constraint(nodes.keys(),T,rule=Battery_P_limits)
    model.solar_P_limits = Constraint(nodes.keys(),T,rule=Solar_P_limits)
    #model.meter_sign_constraint = Constraint(nodes.keys(), T, rule=sign_constraint_rule1)
    #model.meter_sign_constraint2 = Constraint(nodes.keys(), T, rule=sign_constraint_rule2)
    model.meter_components_rule = Constraint(nodes.keys(), T, rule = P_meter_components_rule)
    model.export_bounds = Constraint(nodes.keys(), T, rule = P_export_bounds)
    model.import_bounds = Constraint(nodes.keys(), T, rule = P_import_bounds)
    
    model.import_constraint = Constraint(nodes.keys(), T, rule = P_import_sign_rule)
    model.export_constraint = Constraint(nodes.keys(), T, rule = P_export_sign_rule)
    model.SOC_P_relationship = Constraint(nodes.keys(),T, rule = delta_SOC_relationship)
    model.Pbatt_limited_by_SOC1 = Constraint(nodes.keys(),T, rule = P_batt_energy_rule1)
    model.Pbatt_limited_by_SOC2 = Constraint(nodes.keys(),T, rule = P_batt_energy_rule2)
    #model.battery_availability = Constraint(nodes.keys(),T,rule=availiable_energy_constraint)
    model.SOC_minmax = Constraint(nodes.keys(), T, rule = SOC_limits)
    
    #FCAS Constraint Declarations
    #model.R_bid_frac_bound = Constraint(T, rule = R_bid_frac_bounds)
    #model.L_bid_frac_bound = Constraint(T, rule = L_bid_frac_bounds)
    #model.R_frac_part_constraint = Constraint(T, rule = Agg_R_fraction_rule)
    #model.L_frac_part_constraint = Constraint(T, rule = Agg_L_fraction_rule)
    
    model.agg_bid_R_constraint = Constraint(T, rule = Aggregate_R_bids)
    model.agg_bid_L_constraint = Constraint(T, rule = Aggregate_L_bids)
    
    
    model.R_batt_power_constr = Constraint(nodes.keys(), T, rule = R_battery_bounds)
    model.RP_batt_constr = Constraint(nodes.keys(), T, rule = R_battery_P_rule)
    model.R_batt_energy_constr = Constraint(nodes.keys(), T, rule = R_battery_energy)
    model.R_bid_constr = Constraint(nodes.keys(), T, rule = R_bid_constraint)
    
    model.L_batt_power_constr = Constraint(nodes.keys(), T, rule = L_battery_bounds)
    model.LP_batt_constr = Constraint(nodes.keys(), T, rule = L_battery_P_rule)
    model.L_batt_energy_constr = Constraint(nodes.keys(), T, rule = L_battery_energy)
    model.L_solar_constraint = Constraint(nodes.keys(), T, rule = L_solar_bounds)
    model.LP_solar_constr = Constraint(nodes.keys(), T, rule = L_solar_P_rule)
    model.L_bid_constr = Constraint(nodes.keys(), T, rule = L_bid_constraint)

#Connectivity

    if aggregator['Behaviour'] == 'Non-strategic':
        model.availability_constraint = Constraint(nodes.keys(), T, rule = random_online_status)
    elif aggregator['Behaviour'] == 'Strategic':
        model.availability_constraint = Constraint(T, rule = Offline_within_reason)
        
        #Do something to ensure strategic online/offline determination.
    log.info('Finished building aggregator model. Returning model.')
    solver = SolverFactory('cplex',executable = '/opt/ibm/ILOG/CPLEX_Studio2211/cplex/bin/x86-64_linux/cplex')
    
    #results = solver.solve(model)
    return model#, solver#, results

    
#Note, for the below function, pay attention to the use of 't' rather than 'T' - current timestep, not all.
def Add_DOE_Constraints(aggregator,model,t):
    nodes = aggregator['Nodes']
    for index in model.import_IOE.index_set():
        model.import_IOE[index].fix()
        model.export_IOE[index].fix()
        model.Online[index].fix()
        model.set_import_IOE[index].deactivate()
        model.set_export_IOE[index].deactivate()
    # for n in nodes.keys():
    #     model.no_breach_penalty[n,t].deactivate()
        
    def R_DOE_compliance(m,n,t):
        return m.P_meter[n,t] - m.R_bid[n,t] >= nodes[n]['export_DOE'][t]
    def L_DOE_compliance(m,n,t):
        return m.P_meter[n,t] + m.L_bid[n,t] <= nodes[n]['import_DOE'][t]
    
    def import_DOE_rule(m,n,t):
        return m.P_import[n,t] - nodes[n]['import_DOE'][t] <= 1000000*m.import_doe_breach[n,t]
    def export_DOE_rule(m,n,t):
        return nodes[n]['export_DOE'][t] + m.P_export[n,t] <= 1000000*m.export_doe_breach[n,t]
    
    
  
    model.import_doe_constraint = Constraint(nodes.keys(), [t], rule=import_DOE_rule)
    model.export_doe_constraint = Constraint(nodes.keys(), [t], rule=export_DOE_rule)
    model.raise_doe = Constraint(nodes.keys(), [t], rule = R_DOE_compliance)
    model.lower_doe = Constraint(nodes.keys(), [t], rule = L_DOE_compliance)
    #return model
    
def Write_Prediction_Data(aggregator,model,t):
    nodes = aggregator['Nodes'].keys()
    
    for node in nodes:
        aggregator['Nodes'][node]['import_IOE'][t] = model.import_IOE[node,t].value
        aggregator['Nodes'][node]['export_IOE'][t] = model.export_IOE[node,t].value
        aggregator['Nodes'][node]['Online'][t] = model.Online[node,t].value
        
def Write_All_Data(aggregator,model,t):
    
    def node_settlement(n):
        node = aggregator['Nodes'][n]
        if node['R_bid'][t] <= 0:
            rbid = 0
        else:
            rbid = node['R_bid'][t]
            
        if node['L_bid'][t] <= 0:
            lbid = 0
        else:
            lbid = node['L_bid'][t]
        
        
        fcas_rev = (node['raise_price'][t]*rbid + node['lower_price'][t]*lbid)*conf.interval_duration
        if node['P_meter'][t] >= 0:
            tariff_cost = node['P_meter'][t]*conf.interval_duration*node['import_price'][t]
        else:
            tariff_cost = node['P_meter'][t]*conf.interval_duration*node['export_price'][t]
        return fcas_rev - tariff_cost
    
    nodes = aggregator['Nodes'].keys()
    for node in nodes:
        aggregator['Nodes'][node]['P_solar'][t] = model.P_solar[node,t].value
        aggregator['Nodes'][node]['P_meter'][t] = model.P_meter[node,t].value
        aggregator['Nodes'][node]['P_batt'][t] = model.P_batt[node,t].value
        aggregator['Nodes'][node]['SOC'][t] = model.SOC[node,t+1].value
        aggregator['Nodes'][node]['Online'][t] = model.Online[node,t].value
        aggregator['Nodes'][node]['R_bid'][t] = model.R_bid[node,t].value
        aggregator['Nodes'][node]['L_bid'][t] = model.L_bid[node,t].value
        aggregator['Nodes'][node]['settled_revenue'][t] = node_settlement(node)
        aggregator['Nodes'][node]['DOE_Breach'][t] = model.import_doe_breach[node,t].value+model.export_doe_breach[node,t].value
        
        