#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Aug 26 23:31:41 2023

@author: marlon
"""
import math as m
import pandas as pd
import logging as log
import pyomo.environ as pyo

#Tooling
cplex_path = '/opt/ibm/ILOG/CPLEX_Studio2211/cplex/bin/x86-64_linux/cplex'
RAM = 24000 #MB RAM - do not overshoot physical RAM. Leave some for operating system processes. Set emphasis below to 'True' to use swap/disk on a low-RAM machiine.
set_memory_emphasis = False #Needed for <6GB usable RAM.
#GENERAL

duration = 30 #days
interval_duration = 5/60 #5min intervals, in hours.
number_of_intervals = m.ceil(24*duration/interval_duration)
agg_optimisation_horizon = 24 #hours
horizon_intervals = agg_optimisation_horizon/interval_duration
nu = 0.05 #fraction of expected/allowable offline nodes
t_start = 3456 #First interval to run on. t=0 is reserved for initialisation.
t_end = number_of_intervals - agg_optimisation_horizon #If we end after this, the opt horizon is insufficient.
current_experiment = {}
cf_import = 0.9 #Import constraint factor used by the strategic IOE calculator to estimate network constraint.
cf_export = 0.9 #Export "" ""
#DSO
#

dso_inputs = {
        'lines' :       pd.read_csv('dso_data/lines.csv'),
        'buses' :       pd.read_csv('dso_data/buses.csv'),
        'V_max' :       1.04,
        'V_min' :       0.96,
        'V_ref':        1.01,
        
        }

feeder = {'is_built': False} 



#Aggregators

aggregators = [
    {
      'AggregatorID' : 1,
      'Number of Nodes' : 30,
      'Behaviour' : 'Strategic',
      'Nodes' : dict(),
      'Expected Offline Fraction': nu,
      },
    {
      'AggregatorID' : 2,
      'Number of Nodes' : 30,
      'Behaviour' : 'Non-strategic',
      'Nodes': dict(),
      'Expected Offline Fraction' : nu,
      }
    ]

load_nodes = {
    'Number of Nodes' : 10,
    'Nodes': dict(),
    }

# load_profiles = pd.read_csv('aggregator_data/load_profiles.csv')
# solar_profiles = pd.read_csv('aggregator_data/solar_profiles.csv')
# tariff = pd.read_csv('aggregator_data/tariff.csv')
# fcas_prices = pd.read_csv('aggregator_d10,ata/fcas_prices.csv')
# batteries = pd.read_csv('aggregator_data/batteries.csv')

aggregator_inputs = {
    'load_profiles'     :   pd.read_csv('aggregator_data/load_profiles_new.csv'),
    'solar_profiles'    :   pd.read_csv('aggregator_data/solar_profiles_expanded.csv'),
    'tariff'            :   pd.read_csv('aggregator_data/tariff.csv'),
    'batteries'         :   pd.read_csv('aggregator_data/batteries.csv'),    
    'fcas_prices'       :   pd.read_csv('aggregator_data/fcas_prices.csv')[120:], #UTC to AEST (in intervals) correction :facepalm:
    }

log.info('Configuration data imported.')

#### Additional options for DSO inputs, used in ConfigureExperiments.py

dso_options = [ #Options for conf.dso_inputs
    {
            'lines' :       pd.read_csv('dso_data/lines.csv'),
            'buses' :       pd.read_csv('dso_data/buses.csv'),
            'V_max' :       1.05,
            'V_min' :       0.95,
            'V_ref':        1.01,
            
            },
    {
            'lines' :       pd.read_csv('dso_data/lines.csv'),
            'buses' :       pd.read_csv('dso_data/buses.csv'),
            'V_max' :       1.04,
            'V_min' :       0.96,
            'V_ref':        1.01,
            
            },
    ]








#Shortuts for tunable solver instances

def AggregatorSolver():
    solver = pyo.SolverFactory('cplex', executable = cplex_path)
    memstring = 'set workmem '+str(RAM)
    solver.options[memstring]
    solver.options['set mip strategy heuristicfreq -1']
    #solver.options['set preprocessing presolve n']
    solver.options['set cpumask 003F']
    solver.options['set emphasis mip 0']
    #solver.options['set threads 6']
    if set_memory_emphasis:
        solver.options['set emphasis memory 1']
    
        
    return solver

def DSOSolver():
    solver = pyo.SolverFactory('cplex', executable = cplex_path)
    memstring = 'set workmem '+str(RAM)
    solver.options[memstring]
    solver.options['set barrier qcpconvergetol 1e-06']
    #should not need memory emphasis enabled.
    return solver