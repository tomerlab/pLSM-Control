# Python 2/3 compatibility.
from __future__ import print_function
import sys
import os
# os.system('sh -c \'echo 2000 > /sys/module/usbcore/parameters/usbfs_memory_mb\'')

import io
import numpy as np
import scipy
from scipy import interpolate

sys.path.append('../')
sys.path.append('../../')
import pprint
import time
import datetime
import pandas as pd
import threading
import PIL
from ipywidgets import interact, interactive, fixed, interact_manual, Video
import ipywidgets as widgets
import IPython.display as ipd
from ipyfilechooser import FileChooser
import pause
import queue
import gc

class ExperimentControl(object):
    def __init__(self, camera, illumination, stage, widgets):
        self.camera = camera
        self.illumination = illumination
        self.stage = stage
        self.widgets = widgets
        self.inExperiment = False
        self._imgBuffer = []
        self._filename = []
    
    
    def realtimeScanning_experiment_control(self, scanningVolume, scanningDuration, scanningInterval, \
                                            scanningRange, scanningStep, lightSheetOffset, outputPath):
        
        if self.camera.enable == True or self.illumination[self.widgets.illumSide_w.index].enable == True:
            self.widgets.warning.value = f"<b><font color='red'>Please stop acquisition and laser before starting experiment.</b>"
            return 0
        
        self.widgets.status.value = 'Start Scanning'
        
        expCurrImgID = 0
        expStartTime = time.time()

        self.make_directory(outputPath)
        self.widgets.save_metadata_file(outputPath)
        ## Experiment loop
        trial = 0
        while(True):
            self.start_experiment()

            ## One imaging period
            acquire_thread = threading.Thread(target = self.acquire_image_thread, args=())
            acquire_thread.start()

            save_thread = threading.Thread(target = self.save_image_thread, args=())
            save_thread.start()

            expPeriodStartTime = time.time()

            for volumes in range(scanningVolume): 
                scanNum = np.ceil((scanningRange+0.5)/scanningStep)
                offsetStart = np.ceil(lightSheetOffset - scanningRange/2)
                
                for offset in range(int(offsetStart), int(offsetStart + scanNum * scanningStep), int(scanningStep)):
                    frameStartTime = time.time()
                    self.widgets.status.value = 'Trial{0:04d}-'.format(trial) + \
                                 'Volume{0:03d}-'.format(volumes) + 'LightSheetOffset{0:03d}'.format(offset)
                    ## Update illumination after exposure

#                     if offset + scanningStep <= lightSheetOffset + round(scanningRange/2):
#                         self.illumination[self.widgets.illumSide_w.index].set_illumination_offset(offset + scanningStep)
#                     else:
#                         self.illumination[self.widgets.illumSide_w.index].set_illumination_offset(
#                             lightSheetOffset - round(scanningRange/2))
                    self.illumination[self.widgets.illumSide_w.index].set_illumination_offset(offset)
    
                    time.sleep(0.008)

                    ## Take image
                    self.camera.trigger_images() 
#                     self._filename += [outputPath + '/{0:08d}-'.format(expCurrImgID) + \
#                                  'V{0:03d}-'.format(volumes) + 'S{0:03d}-'.format(offset) +
#                                  time.strftime("%m-%d-%Y-%H-%M-%S", time.localtime())]   

                    self._filename.put(outputPath + '/{0:08d}-'.format(expCurrImgID) + 'Trial{0:04d}-'.format(trial) + \
                                 'V{0:03d}-'.format(volumes) + 'S{0:03d}-'.format(offset) +
                                 time.strftime("%m-%d-%Y-%H-%M-%S", time.localtime()) )
                    expCurrImgID += 1

                    frameSpentTime = time.time() - frameStartTime
                    time.sleep(np.max([1/self.camera.framerate - frameSpentTime, 1e-6]))
                ## End scanning frames
                # illumination.dark()
            ## End scanning volumes

            expCurrTime = time.time()

            expPeriodTime = time.time() - expPeriodStartTime

#             illumination.dark()
#             camera.stopFlag = True    
            self.end_experiment()
            trial += 1
            if expCurrTime + scanningInterval*60 - expPeriodTime - expStartTime + 5 >= \
            scanningDuration*60:
                break

            time.sleep(scanningInterval*60 - expPeriodTime)

#         camera.cam.EndAcquisition()
#         camera.OnExperiment = False    

            
        
    def widefield_experiment_control(self, outputPath, totalFrames):
        
        if self.camera.enable == True or self.illumination[self.widgets.illumSide_w.index].enable == True:
            self.widgets.warning.value = f"<b><font color='red'>Please stop acquisition and laser before starting experiment.</b>"
            return 0
        
        self.start_experiment()
        self.illumination[self.widgets.illumSide_w.index].update()
        
        self.make_directory(outputPath)     
        self.widgets.save_metadata_file(outputPath)
        
        self.totalFrames = totalFrames
        self.readCounts = 0
        self.savedCounts = 0
        
        acquire_thread = threading.Thread(target=self.acquire_image_thread, args=())
        acquire_thread.start()

        save_thread = threading.Thread(target=self.save_image_thread, args=())
        save_thread.start()

        for curFrame in range(totalFrames):

            frameStartTime = time.time()

            ## Take image
            self.camera.trigger_images() 
            
            self._filename.put(outputPath + r'/{0:08d}-'.format(curFrame) + \
                         time.strftime("%m-%d-%Y-%H-%M-%S", time.localtime()))
            ## Update illumination after exposure
            frameSpentTime = time.time() - frameStartTime
            time.sleep(np.max([1/self.camera.framerate - frameSpentTime, 1e-6]))
        
        time.sleep(15)
        self.end_experiment()
        
    
    def largeFOV_experiment_control(self, minX, maxX, minY, maxY, minZ, maxZ, \
                                    deltaZ, overlap, cameraX, cameraY, alignment_array, outputPath):
        
        if self.camera.enable == True or self.illumination[0].enable == True:
            self.widgets.warning.value = f"<b><font color='red'>Please stop acquisition and laser before starting experiment.</b>"
            return 0
        
        
        
        ## LIGHT SHEET ALIGNMENT 
#         xStep = (1-overlap/100)*1.6 #10x
#         xStep = (1-overlap/100)*0.86 #ASI 16x
        xStep = (1-overlap/100)*cameraX
        x = np.arange(minX, maxX + xStep - 0.05, xStep)
        
#         yStep = (1-overlap/100)*0.7 #10x
#         yStep = (1-overlap/100)*0.45 #ASI 16x
        yStep = (1-overlap/100)*cameraY
        y = np.arange(minY, maxY + yStep - 0.05, yStep)
        
        z = np.arange(minZ, maxZ, deltaZ)
        
        #mask invalid values
        xx, yy, zz = np.meshgrid(x, y, z, indexing = 'ij')

        if np.array(alignment_array).shape[0] < 5:
            offsetFinal = [np.ones((len(x),len(y),len(z)))*self.widgets.lightSheetOffset_w.value] * 2
        else:
            offsetFinal = [None]*2
            for lightsheetID in range(len(self.illumination)):
                try:
                    offsetLinearInterp = interpolate.griddata(alignment_array[:,:3], alignment_array[:,3 + lightsheetID],
                                          (xx, yy, zz),
                                             method='linear')
                except Exception as error:
                    if 'scipy.spatial.qhull.QhullError' in str(type(error)):
                        self.widgets.warning.value = f"<b><font color='red'>Light Sheet Offset Interpolation Error. Possible: Anchor points rank low.</b>"
#                         self.end_experiment()

                        return

                offsetLinearInterpInvalid = np.ma.masked_invalid(offsetLinearInterp)

                x1 = xx[~offsetLinearInterpInvalid.mask]
                y1 = yy[~offsetLinearInterpInvalid.mask]
                z1 = zz[~offsetLinearInterpInvalid.mask]
                newarr = offsetLinearInterpInvalid[~offsetLinearInterpInvalid.mask]
                

                try:
                    offsetFinal[lightsheetID] = np.round(interpolate.griddata((x1, y1, z1), newarr.ravel(),
                                              (xx, yy, zz),
                                                 method='nearest'), 0).astype('int16')
                except IndexError as error:
                    self.widgets.warning.value = f"<b><font color='red'>Light Sheet Offset Interpolation Error. Possible: Anchor points convex hull outside area.</b>"
#                     self.end_experiment()
                    
                    return


            
            del offsetLinearInterp, offsetLinearInterpInvalid
            del x1, y1, z1, newarr
        del xx, yy, zz
        gc.collect()

        
        self.make_directory(outputPath) 

        ## CHANNEL SELECTION
        channels = []
        if self.widgets.red_w.value != 0:
            channels += ['0x' + hex(self.widgets.red_w.value + 256)[-2:] + '0000']
        if self.widgets.green_w.value != 0:
            channels += ['0x00' + hex(self.widgets.green_w.value + 256)[-2:] + '00']
        if self.widgets.blue_w.value != 0:
            channels += ['0x0000' + hex(self.widgets.blue_w.value + 256)[-2:]]


        self.widgets.save_metadata_file(outputPath)
        
#         acquire_thread = threading.Thread(target=self.acquire_image_thread, args=())
#         acquire_thread.start()

#         save_thread = threading.Thread(target=self.save_image_thread, args=())
#         save_thread.start()
        self.start_experiment()
        self.stage.move('X', x[0])
        time.sleep(5)
        self.stage.move('Y', y[0])
        time.sleep(5)
        
        for scanX in range(len(x)):
            self.stage.move('X', x[scanX])
            time.sleep(2.5)
            self.is_stage_moving('X', x[scanX])
            for scanY in range(len(y)):            
                self.stage.move('Y', y[scanY])
                time.sleep(2.5)
                self.is_stage_moving('Y', y[scanY])
#                 if (scanX < 2) or (scanX == 2 and scanY < 6):
#                     continue
                for CHN in range(len(channels)):
                    time.sleep(2.5)
                    
                    self.illumination[0].dark()
                    if len(self.illumination) > 1:
                        self.illumination[1].dark()
                    self.stage.move('Z', z[0])
                    time.sleep(5)
                    self.is_stage_moving('Z', z[0])
                    gc.collect()    
                    
                    # Setup camera
                    self.empty_camera_buffer()
                    if scanY < len(y)/2:
                        self.camera.exposure = np.around(self.widgets.exposure_w.value/16.83) * \
                                                         self.widgets.exposureStepLS1.value*1000
                    else:
                        self.camera.exposure = np.around(self.widgets.exposure_w.value/16.83) * \
                                                         self.widgets.exposureStepLS2.value*1000
#                     self.camera.AnalogControl() 
                    
                    # Decide which arm to use
                    if self.widgets.imagingArm_w.index == 2:
                        if scanY < len(y)/2:
                            arm = 0
                        else:
                            arm = 1
                    else:
                        arm = self.widgets.imagingArm_w.index
                            
                    locPath = outputPath + '/LOC{0:03d}'.format(scanY*len(x) + scanX)
                    self.make_directory(locPath) 

                    self.illumination[arm].fg_color = int(channels[CHN], 16)
                    self.illumination[arm].set_illumination_offset(int(offsetFinal[arm][scanX, scanY, 0]))
                    preOffset = 1000
                    for scanZ in range(len(z)):
                        

                        self.stage.move('Z', z[scanZ])                        
                        
                        self.illumination[arm].fg_color = int(channels[CHN], 16)
                        currOffset = int(offsetFinal[arm][scanX, scanY, scanZ])
                        if currOffset != preOffset:
                            self.illumination[arm].set_illumination_offset(currOffset)
                            time.sleep(0.032)
                            preOffset = currOffset
                        
                        self.is_stage_moving('Z', z[scanZ])
                        frameStartTime = time.time()
                        
                        ## Take image
                        self.camera.trigger_images() 
                        
                        
#                         self._filename.put(fileName)

#                         time.sleep(0.032)
    
                        img = self.camera.cam.GetNextImage(300000).GetNDArray().copy()
                        fileName = locPath + \
                                     '/{0:03d}-{1:03d}-{2:04d}-CHN{3:02d}-'.format(scanX,scanY,scanZ,CHN) +  \
                                     time.strftime("%m-%d-%Y-%H-%M-%S", time.localtime())
                        
                        img.tofile(fileName)
                    
                        ## Update illumination after exposure
                        frameSpentTime = time.time() - frameStartTime
                        time.sleep(np.max([1/self.camera.framerate - frameSpentTime, 1e-6]))
    #                     illumination.dark()
                    
            ## End scanning frames

        ## End scanning volumes
        time.sleep(5)
        self.end_experiment()
        return
    
        
        
    def start_experiment(self):
        self._imgBuffer = queue.Queue(maxsize = 50)
        self._filename = queue.Queue(maxsize = 50)
        self.inExperiment = True
        
        self.illumination[0].enable = True
        if len(self.illumination) > 1:
            self.illumination[1].enable = True
            
        self.camera.enable = True
        self.camera.cam.BeginAcquisition()

        ## Empty camera buffer
        self.empty_camera_buffer()
        return
    
    def end_experiment(self):
        self.illumination[0].dark()
        self.illumination[0].enable = False
        if len(self.illumination) > 1:
            self.illumination[1].dark()
            self.illumination[1].enable = False
        time.sleep(2.5)
        for _ in range(15):
            if self._imgBuffer.qsize() > 0 and self._filename.qsize() > 0:
                time.sleep(20)
#             if len(self._imgBuffer) > 0 and len(self._filename) > 0 :
#                 time.sleep(20)
        self.camera.cam.EndAcquisition()
        self.camera.enable = False        
        
        self.inExperiment = False
        return
    
    def empty_camera_buffer(self):
        for _ in range(200):
            try:
                self.camera.cam.GetNextImage(int(self.camera.exposure/1e3) + 10).GetNDArray().copy()
            except:
                break
        return
    
    def acquire_image_thread(self):
        while self.inExperiment == True:
            try:
                self._imgBuffer.put(self.camera.cam.GetNextImage(300000).GetNDArray().copy())
                self.readCounts += 1
            except:
                1
        return
    
    def is_stage_moving(self, iStage, pos):
        posPre = self.stage.get_position(iStage)
        for i in range(500):
            time.sleep(0.005)
            posNow = self.stage.get_position(iStage)
            if  (np.abs(posPre - pos) < 8e-3) and (np.abs(posNow - pos) < 8e-3): # (np.abs(posNow - posPre) < 2e-6) and
                # if stage stopped moving And stage reaches close to target location
                break
            posPre = posNow
        return
                
    def save_image_thread(self):   
        while self.inExperiment == True or self.saveCounts < self.totalFrames:
            try:
                
                while self.inExperiment == True and (self._imgBuffer.qsize() == 0 or self._filename.qsize() == 0) :
                    1
                
                self._imgBuffer.get().tofile(self._filename.get())
                self.saveCounts += 1
            except:
                1
        print('Save thread End')
        return       
    
        
    def make_directory(self, path):
        if not os.path.isdir(path):
            os.mkdir(path)
        return    

            