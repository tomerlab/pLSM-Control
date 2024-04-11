# Python 2/3 compatibility.
from __future__ import print_function
import sys
import os
import io
sys.path.append('../')
import time
import numpy as np
import PIL

from Xlib import X, display, Xutil
from Xlib.ext import randr, xinerama

import PySpin


class Camera(object):
    def __init__(self, cam, width = 2048, height = 1500, binning = 1, \
                 exposure = 100000, framerate = 10, \
                pixelFormat = 8, gain = 10):
        
        self.stopFlag = False
        self.enable = False
        self.cam = cam
        self.exposure = exposure
        self.framerate = framerate
        formats = {8:'Mono8', 16:'Mono16'}
        self.pixelFormat = formats[pixelFormat]
        self.width = int(np.min([width, 5000]))
        self.height = int(np.min([height, 3000]))
        self.binning = binning
        self.trigger = []
        
        self.gain = gain
        self.t0 = 0
        self.currImage = np.zeros((width, height))
        self.currFrame = 0
        self.nodemap = []
        self.acquisitionOn = False
        self.info = ''
        
        self.OnExperiment = False
        self.ExpDuration = 0
        self.ExpInter = 0
        self.ExpFrame = 4
        self.ExpPath = os.getcwd()
        
    def setup_single_camera(self, isPrint = False):
        try:
            result = True

            # Retrieve TL device nodemap and print device information
            nodemap_tldevice = self.cam.GetTLDeviceNodeMap()
            if isPrint:
                result &= self.print_device_info(nodemap_tldevice)
            
            # Initialize camera
            self.cam.Init()
            
            # Retrieve GenICam nodemap
            self.nodemap = self.cam.GetNodeMap()
            
            # Configure exposure
            result &= self.TriggerControl()
            result &= self.AcquisitionControl()
            result &= self.ImageFormatControl()
            result &= self.AnalogControl()
            self.enable = False
#             self.cam.BeginAcquisition()

        except PySpin.SpinnakerException as ex:
            print('Error: %s' % ex)
            result = False
            
        return result
    
    
    def print_device_info(self, nodemap):

        print('\n*** DEVICE INFORMATION ***\n')

        try:
            result = True
            node_device_information = PySpin.CCategoryPtr(nodemap.GetNode('DeviceInformation'))

            if PySpin.IsAvailable(node_device_information) and PySpin.IsReadable(node_device_information):
                features = node_device_information.GetFeatures()
                for feature in features:
                    node_feature = PySpin.CValuePtr(feature)
                    print('%s: %s' % (node_feature.GetName(),
                                      node_feature.ToString() \
                                      if PySpin.IsReadable(node_feature) else 'Node not readable'))

            else:
                print('Device control information not available.')

        except PySpin.SpinnakerException as ex:
            print('Error: %s' % ex)
            return False

        return result

    
    
    def trigger_images(self):
        try:
            result = True
            
            self.t0 = 0
            if self.enable == True:
                self.trigger.Execute()
            
            
        except PySpin.SpinnakerException as ex:
            print('Error: %s' % ex)
            
            try: 
                self.setup_single_camera()
                self.trigger.Execute()
                return True
            except PySpin.SpinnakerException as ex:
                print('Error: %s' % ex)
                return False
            

        return result
    
    def TriggerControl(self):
        try:
            result = True
            
            nodemap = self.cam.GetNodeMap()
            node_user_set = PySpin.CEnumerationPtr(nodemap.GetNode('UserSetSelector'))
            node_user_set.SetIntValue(PySpin.UserSetDefault_Default)
            
            node_trigger_mode = PySpin.CEnumerationPtr(nodemap.GetNode('TriggerMode'))
            node_trigger_mode.SetIntValue(0)
            
            node_trigger_selector = PySpin.CEnumerationPtr(nodemap.GetNode('TriggerSelector'))
            node_trigger_selector.SetIntValue(0)
            
            node_trigger_source = PySpin.CEnumerationPtr(nodemap.GetNode('TriggerSource'))
            node_trigger_source_software = node_trigger_source.GetEntryByName('Software')
            node_trigger_source.SetIntValue(node_trigger_source_software.GetValue())
            
            node_trigger_activation = PySpin.CEnumerationPtr(nodemap.GetNode('TriggerActivation'))
            node_trigger_activation.SetIntValue(1)
#             node_trigger_activation_mode = node_trigger_activation.GetEntryByName('RisingEdge')
#             node_trigger_activation.SetIntValue(node_trigger_activation_mode.GetValue())
            
            node_trigger_mode.SetIntValue(1)
            
            node_trigger_overlap = PySpin.CEnumerationPtr(nodemap.GetNode('TriggerOverlap'))
            node_trigger_overlap.SetIntValue(1)
            
            self.trigger = PySpin.CCommandPtr(self.nodemap.GetNode('TriggerSoftware'))
            
        except PySpin.SpinnakerException as ex:
            print('Error: %s' % ex)
            result = False

        return result
    def AcquisitionControl(self):
#         print('\n*** CONFIGURING ACQUISITION ***\n')
        
        try:
            result = True
            
            nodemap = self.cam.GetNodeMap()
            node_user_set = PySpin.CEnumerationPtr(nodemap.GetNode('UserSetSelector'))
            node_user_set.SetIntValue(PySpin.UserSetDefault_Default)
            
            node_exposure_comp_mode = PySpin.CEnumerationPtr(nodemap.GetNode('pgrExposureCompensationAuto'))
            node_exposure_comp_mode_type = node_exposure_comp_mode.GetEntryByName('Off')
            node_exposure_comp_mode.SetIntValue(node_exposure_comp_mode_type.GetValue())
            
            try:
                black_clamp_enabled = PySpin.CBooleanPtr(nodemap.GetNode('BlackLevelClampingEnable'))
                black_clamp_enabled.SetValue(False)
            except:
                1
            
#             node_exposure_comp = PySpin.CFloatPtr(nodemap.GetNode('pgrExposureCompensation'))
#             node_exposure_comp.SetValue(0)
            
            # Configure acquisition mode
            node_acquisition_mode = PySpin.CEnumerationPtr(nodemap.GetNode('AcquisitionMode'))
            node_acquisition_mode_SingleFrame = node_acquisition_mode.GetEntryByName('Continuous')
            node_acquisition_mode.SetIntValue(node_acquisition_mode_SingleFrame.GetValue())
#             print('Acquisition mode set to continuous...')
            


            # Configure exposure time
            node_exposure_mode = PySpin.CEnumerationPtr(nodemap.GetNode('ExposureMode'))
            node_exposure_mode_timed = node_exposure_mode.GetEntryByName('Timed')
            node_exposure_mode.SetIntValue(node_exposure_mode_timed.GetValue())
#             print('Exposure mode set to timed...')
            
            node_exposure_auto = PySpin.CEnumerationPtr(nodemap.GetNode('ExposureAuto'))
            node_exposure_auto_off = node_exposure_auto.GetEntryByName('Off')
            node_exposure_auto.SetIntValue(node_exposure_auto_off.GetValue())
#             print('Automatic exposure disabled...')
            time.sleep(0.3)
            exposure_time_to_set = min(self.cam.ExposureTime.GetMax(), self.exposure)
            node_exposure_time = PySpin.CFloatPtr(nodemap.GetNode('ExposureTime'))
            node_exposure_time.SetValue(exposure_time_to_set)
#             print('Shutter time set to %s us...\n' % exposure_time_to_set)
            
        except PySpin.SpinnakerException as ex:
            print('Error: %s' % ex)
            result = False

        return result
    
    def ImageFormatControl(self):
#         print('\n*** CONFIGURING IMAGE SETTINGS ***\n')

        try:
            result = True
            nodemap = self.cam.GetNodeMap()
            # Set pixel format    
            node_pixel_format_mode = PySpin.CEnumerationPtr(nodemap.GetNode('PixelFormat'))
            try:
                node_pixel_format_mode_entry = node_pixel_format_mode.GetEntryByName(self.pixelFormat)
                node_pixel_format_mode.SetIntValue(node_pixel_format_mode_entry.GetValue())
#                 print('Pixel format set to %s...' % self.pixelFormat)
            except:
                1
#                 print('Pixel format not available for hot change')

            if self.cam.OffsetX.GetAccessMode() == PySpin.RW:
                self.cam.OffsetX.SetValue(self.cam.OffsetX.GetMin())
                1
#                 print('Offset X set to %d...' % self.cam.OffsetX.GetValue())
            else:
#                 print('Offset X not available...')
                result = False

            if self.cam.OffsetY.GetAccessMode() == PySpin.RW:
                self.cam.OffsetY.SetValue(self.cam.OffsetY.GetMin())
                1
#                 print('Offset Y set to %d...' % self.cam.OffsetY.GetValue())
            else:
#                 print('Offset Y not available...')
                result = False
            node_bin_h = PySpin.CIntegerPtr(nodemap.GetNode('BinningVertical'))
            node_bin_h.SetValue(self.binning)
            
            node_width = PySpin.CIntegerPtr(nodemap.GetNode('Width'))
            self.width = int(np.min([self.width,node_width.GetMax()]))
            node_width.SetValue(self.width)
                                
            
            node_height = PySpin.CIntegerPtr(nodemap.GetNode('Height'))
            self.height = int(np.min([self.height,node_height.GetMax()]))
            node_height.SetValue(self.height)
            print(node_width.GetMax(), node_height.GetMax())
            
            self.currImage = np.zeros((self.width, self.height))                    
            print('Image Shape: ({}, {})'.format(self.height, self.width))
            

        except PySpin.SpinnakerException as ex:
            print('Error: %s' % ex)
            return False

        return result
    
    def AnalogControl(self):
#         print('\n*** CONFIGURING ANALOG SETTINGS ***\n')
        
        try:
            result = True
            nodemap = self.cam.GetNodeMap()
            # Configure gain
            node_gain_auto = PySpin.CEnumerationPtr(nodemap.GetNode('GainAuto'))
            node_gain_auto_off = node_gain_auto.GetEntryByName('Off')
            node_gain_auto.SetIntValue(node_gain_auto_off.GetValue())
#             print('Automatic gain disabled...')
            
            node_gain = PySpin.CFloatPtr(nodemap.GetNode('Gain'))
            node_gain.SetValue(self.gain)
#             print('Gain set to %s ...\n' % self.gain)
            
            try:
                # Configure gamma
                node_gamma_enabled = PySpin.CBooleanPtr(nodemap.GetNode('GammaEnabled'))
                node_gamma_enabled.SetValue(False)
            except:
                1
#                 print('Gamma untouchable')
                
            try:
                # Configure hue
                node_hue_enabled = PySpin.CBooleanPtr(nodemap.GetNode('HueEnabled'))
                node_hue_enabled.SetValue(False) 
            except:
                1
#                 print('Hue untouchable')
               
            try:
                # Configure saturation
                node_saturation_enabled = PySpin.CBooleanPtr(nodemap.GetNode('SaturationEnabled'))
                node_saturation_enabled.SetValue(False) 
            except:
                1
#                 print('Saturation untouchable')
               
            try:
                # Configure sharpness
                node_sharpness_enabled = PySpin.CBooleanPtr(nodemap.GetNode('SharpnessEnabled'))
                node_sharpness_enabled.SetValue(False) 
            except:
                1
#                 print('Sharpness untouchable')
               
#             print('Gamma, hue, saturation, sharpness disabled...')
            
        except PySpin.SpinnakerException as ex:
            print('Error: %s' % ex)
            return False

        return result


