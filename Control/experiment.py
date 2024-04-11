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
    def __init__(self, camera, illumination, widgets):
        self.camera = camera
        self.illumination = illumination
        self.widgets = widgets
        self.inExperiment = False
        self._imgBuffer = []
        self._filename = []
    
    
    def realtimeScanning_experiment_control(self, scanningVolume, scanningDuration, scanningInterval, \
                                            scanningRange, scanningStep, lightSheetOffset, outputPath):
        
        if self.camera.enable == True or self.illumination[self.widgets.illumSide_w.index].enable == True:
            return 0

        expCurrImgID = 0
        expStartTime = time.time()

        self.make_directory(outputPath)
        
        ## Experiment loop
        while(True):
            self.start_experiment()

            ## One imaging period
            acquire_thread = threading.Thread(target = self.acquire_image_thread, args=())
            acquire_thread.start()

            save_thread = threading.Thread(target = self.save_image_thread, args=())
            save_thread.start()

            expPeriodStartTime = time.time()

            for volumes in range(scanningVolume): 

                for offset in range(lightSheetOffset - round(scanningRange/2),
                                    lightSheetOffset + round(scanningRange/2), scanningStep):

                    frameStartTime = time.time()

                    ## Update illumination after exposure

                    if offset + scanningStep <= lightSheetOffset + round(scanningRange/2):
                        self.illumination[self.widgets.illumSide_w.index].set_illumination_offset(offset + scanningStep)
                    else:
                        self.illumination[self.widgets.illumSide_w.index].set_illumination_offset(
                            lightSheetOffset - round(scanningRange/2))

                    time.sleep(0.008)

                    ## Take image
                    self.camera.trigger_images() 
#                     self._filename += [outputPath + '/{0:08d}-'.format(expCurrImgID) + \
#                                  'V{0:03d}-'.format(volumes) + 'S{0:03d}-'.format(offset) +
#                                  time.strftime("%m-%d-%Y-%H-%M-%S", time.localtime())]   

                    self._filename.put(outputPath + '/{0:08d}-'.format(expCurrImgID) + \
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

            if expCurrTime + scanningInterval*60*60 - expPeriodTime - expStartTime + 5 >= \
            scanningDuration*60*60:
                break

            time.sleep(scanningInterval*60*60 - expPeriodTime)

#         camera.cam.EndAcquisition()
#         camera.OnExperiment = False    

            
        
    def widefield_experiment_control(self, outputPath, totalFrames):
        
        if self.camera.enable == True or self.illumination[self.widgets.illumSide_w.index].enable == True:
            return 0
        
        self.start_experiment()
        self.illumination[self.widgets.illumSide_w.index].update()
        
        self.make_directory(outputPath)     
        
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
                
        self.end_experiment()
        
    
    def largeFOV_experiment_control(self, minX, maxX, minY, maxY, minZ, maxZ, \
                                    deltaZ, overlap, alignment_array, outputPath):
        
        if self.camera.enable == True or self.illumination[0].enable == True:
            return 0
        
        self.start_experiment()
        
        self.make_directory(outputPath) 
        
        ## LIGHT SHEET ALIGNMENT 
        xStep = (1-overlap/100)*1.6
        x = np.arange(minX, maxX + xStep - 0.05, xStep)
        yStep = (1-overlap/100)*0.7
        y = np.arange(minY, maxY + yStep - 0.05, yStep)
        z = np.arange(minZ, maxZ, deltaZ)
        #mask invalid values
        xx, yy, zz = np.meshgrid(x, y, z, indexing = 'ij')

        if np.array(alignment_array).shape[0] < 5:
            offsetFinal = [np.ones((len(x),len(y),len(z)))*self.widgets.lightSheetOffset_w.value] * 2
        else:
            offsetFinal = [None]*2
            for lightsheetID in range(len(self.illumination)):
                offsetLinearInterp = interpolate.griddata(alignment_array[:,:3], alignment_array[:,3 + lightsheetID],
                                          (xx, yy, zz),
                                             method='linear')

                offsetLinearInterpInvalid = np.ma.masked_invalid(offsetLinearInterp)

                x1 = xx[~offsetLinearInterpInvalid.mask]
                y1 = yy[~offsetLinearInterpInvalid.mask]
                z1 = zz[~offsetLinearInterpInvalid.mask]
                newarr = offsetLinearInterpInvalid[~offsetLinearInterpInvalid.mask]
                offsetFinal[lightsheetID] = np.round(interpolate.griddata((x1, y1, z1), newarr.ravel(),
                                          (xx, yy, zz),
                                             method='nearest'), 0).astype('int16')
            
            del offsetLinearInterp, offsetLinearInterpInvalid
            del x1, y1, z1, newarr
        del xx, yy, zz
        gc.collect()

#         with open('__lightsheetOffsets__.pkl', 'wb') as f: 
#             pickle.dump([offsetFina], f, pickle.HIGHEST_PROTOCOL)    

        ## CHANNEL SELECTION
        channels = []
        if self.widgets.red_w.value != 0:
            channels += ['0x' + hex(self.widgets.red_w.value + 256)[-2:] + '0000']
        if self.widgets.green_w.value != 0:
            channels += ['0x00' + hex(self.widgets.green_w.value + 256)[-2:] + '00']
        if self.widgets.blue_w.value != 0:
            channels += ['0x0000' + hex(self.widgets.blue_w.value + 256)[-2:]]


        ## IMAGING TIMELINE
        # Relative start time for each tile after clicking Experiment
        tileStartDelta = (np.arange(0, len(x)*len(y)*len(channels)) * (30 + len(z)/self.camera.framerate))

        # Wait time after clicking experiment
        datetimeNow = datetime.datetime.now() + datetime.timedelta(0, 60)
        # Absolute start time for each tile
        tileStartTime = [datetimeNow + datetime.timedelta(0, tileStartDelta[i]) \
                         for i in range(len(tileStartDelta))]

        pd.DataFrame([pd.DataFrame([self.camera.framerate, len(channels)]*len(tileStartTime)), \
                      pd.DataFrame(tileStartTime), pd.DataFrame(x), pd.DataFrame(y), pd.DataFrame(z)] \
                    ).to_pickle(outputPath + '/expList')

        acquire_thread = threading.Thread(target=self.acquire_image_thread, args=())
        acquire_thread.start()

        save_thread = threading.Thread(target=self.save_image_thread, args=())
        save_thread.start()
       
        
        for scanX in range(len(x)):
            for scanY in range(len(y)):
                for CHN in range(len(channels)):
                    gc.collect()
                    self.illumination[0].dark()
                    if len(self.illumination) > 1:
                        self.illumination[1].dark()
                        
                    time.sleep(3)
                    
                    self.empty_camera_buffer()
                    if scanY < len(y)/2:
                        self.camera.exposure = np.around(self.widgets.exposure_w.value/16.83) * \
                                                         self.widgets.exposureStepLS1.value*1000
                    else:
                        self.camera.exposure = np.around(self.widgets.exposure_w.value/16.83) * \
                                                         self.widgets.exposureStepLS2.value*1000
                    self.camera.AnalogControl() 
                    
                    locPath = outputPath + '/LOC{0:03d}'.format(scanY*len(x) + scanX)
                    self.make_directory(locPath) 
                    pause.until(tileStartTime[(scanX*len(y) + scanY)*len(channels) + CHN])
                    preOffset = 1000
                    for scanZ in range(len(z)):
                        frameStartTime = time.time()
                        
                        
#                         if scanY < len(y)/2:
#                             self.illumination[0].fg_color = int(channels[CHN], 16)
#                             currOffset = int(offsetFinal[0][scanX, scanY, scanZ])
#                             if currOffset != preOffset:
#                                 self.illumination[0].set_illumination_offset(currOffset)
                                
#                         else:
                        self.illumination[1].fg_color = int(channels[CHN], 16)
                        currOffset = int(offsetFinal[1][scanX, scanY, scanZ])
                        if currOffset != preOffset:
                            self.illumination[1].set_illumination_offset(currOffset)
                                
                        preOffset = currOffset

#                         self.illumination[0].fg_color = int(channels[CHN], 16)
#                         self.illumination[0].set_illumination_offset(int(offsetFinal[0][scanX, scanY, scanZ]))
#                         if len(self.illumination) > 1:
#                             self.illumination[1].fg_color = int(channels[CHN], 16)
#                             self.illumination[1].set_illumination_offset(int(offsetFinal[1][scanX, scanY, scanZ]))

                        time.sleep(0.032)
                        ## Take image
                        self.camera.trigger_images() 
                        self._filename.put(locPath + \
                                     '/{0:03d}-{1:03d}-{2:04d}-CHN{3:02d}-'.format(scanX,scanY,scanZ,CHN) +  \
                                     time.strftime("%m-%d-%Y-%H-%M-%S", time.localtime()))

                        
                    
                        ## Update illumination after exposure
                        frameSpentTime = time.time() - frameStartTime
                        time.sleep(np.max([1/self.camera.framerate - frameSpentTime, 1e-6]))
    #                     illumination.dark()
                        
                    
            ## End scanning frames

        ## End scanning volumes
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
        time.sleep(5)
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
#         loopcount = 0
        while self.inExperiment == True:
#             loopcount += 1
            try:
#                 print(loopcount)
                self._imgBuffer.put(self.camera.cam.GetNextImage(2000).GetNDArray().copy())
                
#                 self._imgBuffer.append(self.camera.cam.GetNextImage(2000).GetNDArray())
            except:
                1
        print('Acq thread End')
        return

    def save_image_thread(self):   
#         loopcount = 0
        while self.inExperiment == True:
#             loopcount += 1
            try:
#                 while self.inExperiment == True and (len(self._imgBuffer) == 0 or len(self._filename) == 0) :
#                     1

#                 self._imgBuffer[0].tofile(self._filename[0])
#                 self._filename.pop(0)
#                 self._imgBuffer.pop(0)
                
                while self.inExperiment == True and (self._imgBuffer.qsize() == 0 or self._filename.qsize() == 0) :
                    1
                
                self._imgBuffer.get().tofile(self._filename.get())
            except:
                1
        print('Save thread End')
        return       
                
    def make_directory(self, path):
        if not os.path.isdir(path):
            os.mkdir(path)
        return    

            