from __future__ import print_function
import sys
import os
import io
sys.path.append('../')
sys.path.append('../../')
import time
from thorlabs_apt_device import BSC, KDC101
import thorlabs_apt_device
from thorlabs_apt_device import protocol as apt
from thorlabs_apt_device.enums import EndPoint

class Stage(object):
    def __init__(self):
        self.stageInfo = {'X': {'serial_number': '27600995',
                       'controller': 'KDC101',
                       'bay': 0,
                       'max_velocity': 772981.3692 ,
                       'acceleration': 4506,
                       'size': 34554.96,
                       'factor': 34554.96 }, 
                 'Y': {'serial_number': '70869749',
                       'controller': 'BSC203',
                       'bay': 1,
                       'max_velocity': 21987328,
                       'acceleration': 4506,
                       'size': 409600,
                       'factor': 409600},
                 'Z': {'serial_number': '27600977',
                       'controller': 'KDC101',
                       'bay': 0,
                       'max_velocity': 772981.3692 ,
                       'acceleration': 4506,
                       'size': 34554.96,
                       'factor': 34554.96 }}
        self.stage = {'X': [], 'Y': [], 'Z': []}
        
        for iStage in ['X', 'Y', 'Z']:
            if self.stageInfo[iStage]['controller'] == 'BSC203':
                self.stage[iStage] = BSC(serial_number=self.stageInfo[iStage]['serial_number'], 
                                x = 3, home = False, swap_limit_switches=True)
            elif self.stageInfo[iStage]['controller'] ==  'KDC101':
                self.stage[iStage] = KDC101(serial_number=self.stageInfo[iStage]['serial_number'], 
                                home = False)
            else:
                return False
            
            self.stage[iStage].set_home_params(int(self.stageInfo[iStage]['max_velocity']), 0, 
                                               bay = self.stageInfo[iStage]['bay'], channel = 0)
         
            self.stage[iStage].set_jog_params(size = int(self.stageInfo[iStage]['size']), 
                                              acceleration = int(self.stageInfo[iStage]['acceleration']), 
                                      max_velocity= int(self.stageInfo[iStage]['max_velocity']), bay = self.stageInfo[iStage]['bay'])
            
            self.stage[iStage].set_velocity_params(int(self.stageInfo[iStage]['acceleration']), 
                                                   int(self.stageInfo[iStage]['max_velocity']), 
                                           bay = self.stageInfo[iStage]['bay'], channel=0)

    def home(self, iStage):
        stage = self.stage[iStage]
        bay = self.stageInfo[iStage]['bay']
        stage._write(apt.mot_move_home(source=EndPoint.HOST, dest=stage.bays[bay], chan_ident=stage.channels[0]))
        return
    
    def home_all(self):
        for iStage in ['X', 'Y', 'Z']:
            self.home(iStage)
        for i in range(600):
            time.sleep(0.1)
            allHomed = 0
            for iStage in ['X', 'Y', 'Z']:
                allHomed += self.get_position(iStage)
            if allHomed == 0:
                return True
        return False
    
    def isHomed(self, iStage):
        stage = self.stage[iStage]
        bay = self.stageInfo[iStage]['bay']
        return stage.status_[bay][0]['homed']
        
    def move(self, iStage, absPos):
        stage = self.stage[iStage]
        bay = self.stageInfo[iStage]['bay']
        position = int(absPos * self.stageInfo[iStage]['factor'])
        stage._write(apt.mot_move_absolute(source=EndPoint.HOST, dest=stage.bays[bay], chan_ident=stage.channels[0], position=position))
        return
    
    def stop_all(self):
        for iStage in ['X', 'Y', 'Z']:
            self.stage[iStage].stop(immediate=True)
        return
    
    def get_position(self, iStage):
        stage = self.stage[iStage]
        bay = self.stageInfo[iStage]['bay']
        factor = self.stageInfo[iStage]['factor']
        
        return stage.status_[bay][0]['position'] / factor