# Python 2/3 compatibility.
from __future__ import print_function
import sys
import os
import io
import numpy as np
sys.path.append('../')
sys.path.append('../../')
import pprint
import time
import threading
import PIL
from ipywidgets import interact, interactive, fixed, interact_manual, Video
import ipywidgets as widgets
import IPython.display as ipd
from ipyfilechooser import FileChooser
import ipysheet
import pandas as pd
import pickle

from experiment import ExperimentControl


class WidgetsPanel(object):
    def __init__(self, camera, illumination, stage, outputPath):
        
        self.outputPathInit = outputPath
        self._style = {'description_width': 'initial'}
        
        self.camera = camera
        self.illumination = illumination
        self.stage = stage
        self.outputPanel = self.setup_output_panel()
        
        self.load_parameters()
        
        self.experiment = ExperimentControl(self.camera, self.illumination, self.stage, self)
        
        

    def setup_output_panel(self):
        self._outputPath_w = widgets.Text(value = self.outputPathInit, placeholder='Saving path', \
                         description='Saving to:', disabled=False, \
                        layout=widgets.Layout(width='50%'), style = self._style)
        
        exp_notice = widgets.HTML(value = \
                 f"<b><font color='red'></b>")
        self.status = widgets.HTML(value = f"<b>Output Status</b>")
        self.warning = widgets.HTML(value = f"<b><font color='red'></b>")

        exit_button_w = widgets.Button(description='Exit')
        exit_button_w.on_click(self.exit_button_clicked)

                                  
        self.streaming                = self.setup_streaming()
        self.camera_control           = self.setup_camera()
        self.stage_control            = self.setup_stage()
        self.illumination_control     = self.setup_illumination()
                                  
        self.wideField_control        = self.setup_wideField_experiment()
        self.largeFOV_control         = self.setup_largeFOV_experiment()
        self.realtimeScanning_control = self.setup_realtimeScanning_experiment()
                                  
        tab = widgets.Tab(layout=widgets.Layout(width='90%'))
        tab.children = [self.realtimeScanning_control, self.wideField_control, self.largeFOV_control]
        tab.set_title(0, 'Light sheet scan')
        tab.set_title(1, 'Wide Field')
        tab.set_title(2, 'Large FOV')


        experimentPanel = widgets.VBox([widgets.HBox([widgets.VBox([self.camera_control, self.stage_control], 
                                                                   layout=widgets.Layout(width='45%')), \
                                                        self.illumination_control], ), \
                                           exp_notice, self._outputPath_w, self.warning, self.status, tab])
                                  
        outputPanel = widgets.VBox([self.streaming, experimentPanel, exit_button_w])
                                  
        return outputPanel

    def setup_streaming(self):
        # Widgets for streaming
        self.image_w = widgets.Image(format='jpeg',width=300, height=100, layout=widgets.Layout(width='90%'))
        
        f = io.BytesIO()
        imageShow = np.zeros((500, 1000))
        PIL.Image.fromarray(imageShow).convert('RGB').save(f, 'jpeg')
        self.image_w.value = f.getvalue()
        self.image_w.width = min(imageShow.shape[1], 1000)
        self.image_w.height = min(imageShow.shape[0], 500)
        
        self.dynamicRange_w = widgets.IntRangeSlider(min=0, max=2**16-1, value=[0,2**16-1], \
                                                     description='Range', step=1, \
                                                     disabled= False, continuous_update=False, \
                                                     style = self._style, layout=widgets.Layout(width='90%'))
        snapshot_button_w = widgets.Button(description='Snapshot')
        
        # Button responses
        snapshot_button_w.on_click(self.snapshot_button_clicked)   
        
        # Integrate
        streaming_w = widgets.VBox([self.dynamicRange_w, 
                                         snapshot_button_w, 
                                         self.image_w]) 
        return streaming_w
    
    
    
    def setup_camera(self): 
#         self.framerate_w = widgets.FloatSlider(min=0.2, max=30, value=10, step=0.2, description='Frame rate (HZ)', \
#                                 continuous_update=False, layout=widgets.Layout(width='90%'), \
#                                              style = self._style)
        self.framerate_w = widgets.FloatSlider(min=0.005, max=20, value=10, step=0.005, description='Frame rate (HZ)', \
                                continuous_update=False, layout=widgets.Layout(width='90%'), \
                                             style = self._style)
        self.exposure_w = widgets.FloatSlider(min=16.83, max=100, value=16.83, description='Exposure (ms)', \
                                         step = 16.83, continuous_update=False, \
                                         layout=widgets.Layout(width='90%'), style = self._style)
        
        self.gain_w = widgets.IntSlider(min=1, max=47.9, value=1, description='Gain', continuous_update=False, \
                                   layout=widgets.Layout(width='90%'), style = self._style)
        
                                  
        self.exposureStepLS1 = widgets.BoundedFloatText(value=16.83, min=16.5, max=17.3, step=0.01, \
                                              description='Exposure For LS1', \
                                                layout=widgets.Layout(width='60%'), style = self._style)   
        exposureStep_w = widgets.VBox([self.exposureStepLS1])
        if len(self.illumination) > 1:
            self.exposureStepLS2 = widgets.BoundedFloatText(value=16.83, min=16.5, max=17.3, step=0.01, \
                                              description='Exposure For LS2', \
                                                layout=widgets.Layout(width='60%'), style = self._style)
            exposureStep_w = widgets.VBox([self.exposureStepLS1, self.exposureStepLS2])
                                  
                                  
        camera_button_w = widgets.Button(description='Acquisition Off')
        
        camera_button_w.on_click(self.camera_button_clicked)
        
        self.framerate_w.observe(self.listen_camera_framerate, names='value')
                                 
        
        camera_w = interactive(self.interactive_camera_update, framerate = self.framerate_w, \
                               exposure = self.exposure_w, gain = self.gain_w)             
                                  

        camera_control = widgets.VBox([camera_button_w, camera_w, exposureStep_w], 
                                      layout=widgets.Layout(width='95%', border = 'solid 1px'))
                                  
        return camera_control
    
    def setup_stage(self): 
        def stage_home(button):
            stageHome_w.disabled = True
            allHomed = self.stage.home_all()
            for iStage in ['X', 'Y', 'Z']:
                self.stage_w[iStage]['Pos_w'].value = 0
            stageHome_w.disabled = False
            return
        
        self.stage_w = {'X': [], 'Y': [], 'Z': []}
        
        stageHome_w = widgets.Button(description='Home',  layout=widgets.Layout(width='auto'))
        stageHome_w.on_click(stage_home)
        
        for iStage in ['X', 'Y', 'Z']:
            self.stage_w[iStage] = self.setup_singleStage(iStage)
            
        stage_control = widgets.VBox([stageHome_w] + [self.stage_w[iStage]['Box'] for iStage in ['X', 'Y', 'Z']], 
                                     layout=widgets.Layout(width='95%', border = 'solid 1px'))
        return stage_control
        
    def setup_singleStage(self, iStage): 
        isMoving = False
        def stage_update(pos):

            stageUp_w.disabled, stageDown_w.disabled, stagePos_w.disabled = True, True, True
            isMoving = True
            
            posPre = self.stage.get_position(iStage)
            self.stage.move(iStage, pos)
            for i in range(300):
                time.sleep(0.1)
                posNow = self.stage.get_position(iStage)
                if (np.abs(posNow - posPre) < 1e-7) and (np.abs(posNow - pos) < 1e-3) :
                    # if stage stopped moving And stage reaches close to target location
                    break
                posPre = posNow
                
            isMoving = False
            stageUp_w.disabled, stageDown_w.disabled, stagePos_w.disabled = False, False, False
            
            # In case of error accumulation, synchrony of widget value and stage value
            stagePos_w.value = round(self.stage.get_position(iStage), 3)
            return

        def stage_click(button):
            if (button.description == '+') and (not isMoving):
                stagePos_w.value = round(stagePos_w.value + stageStep_w.value, 3)
            elif (button.description == '-') and (not isMoving):
                stagePos_w.value = round(stagePos_w.value - stageStep_w.value, 3)
#             stageUp_w.disable, stageDown_w.disable = True, True
#             time.sleep(0.5)
#             stageUp_w.disable, stageDown_w.disable = True, True
            return
            
        stageName_w = widgets.Label(value='Stage ' + iStage + ' :', 
                                    layout=widgets.Layout(width='auto', grid_area = 'stageName'), style=self._style) 
        stagePos_w = widgets.BoundedFloatText(value=round(self.stage.get_position(iStage), 3), min=0, max=23, 
                                              step=0.001, description='Loc', 
                                              layout=widgets.Layout(width='auto', grid_area = 'stagePos'), style = self._style)   
        stageStep_w = widgets.BoundedFloatText(value=0.5, min=0.001, max=2, step=0.001, description='Step', 
                                              layout=widgets.Layout(width='auto', grid_area = 'stageStep'), style = self._style)
        stageUp_w = widgets.Button(description='+',  layout=widgets.Layout(width='auto', grid_area = 'stageUp'))
        stageUp_w.on_click(stage_click)
        stageDown_w = widgets.Button(description='-', layout=widgets.Layout(width='auto', grid_area = 'stageDown'))
        stageDown_w.on_click(stage_click) 

        interStagePos_w = interactive(stage_update, pos = stagePos_w)
        
        box_w = widgets.HBox([stageName_w, stageDown_w, interStagePos_w, stageUp_w, stageStep_w], layout=widgets.Layout(width='95%',
                                            grid_template_rows = 'auto',
                                            grid_template_columns = '10% 20% 50% 20% 50%',
                                            grid_template_areas = '''
                                                "stageName stageDown stagePos stageUp stageStep"
                                            '''))
        
        return {'Pos_w': stagePos_w, 'Up_w': stageUp_w, 'Down_w': stageDown_w, 'Box': box_w}
    
    
        
    def setup_illumination(self):
        ''' 
            Widgets for illumination control 
            
        '''
        self.red_w = widgets.IntSlider(min=0, max=255, value=0, description='Red', continuous_update=False, \
                           layout=widgets.Layout(width='90%'))
        
        self.green_w = widgets.IntSlider(min=0, max=255, value=0, description='Green', \
                                         continuous_update=False, layout=widgets.Layout(width='90%'))
        
        self.blue_w = widgets.IntSlider(min=0, max=255, value=0, description='Blue', \
                                        continuous_update=False, layout=widgets.Layout(width='90%'))
        
        self.lightSheetWidth_w = widgets.IntSlider(min=0, max=self.illumination[0].sc_W, value=10, \
                                              description='Width', \
                                  continuous_update=False, layout=widgets.Layout(width='90%'))
        
        self.lightSheetHeight_w = widgets.IntSlider(min=0, max=self.illumination[0].sc_H, value=500, \
                                               description='Height', continuous_update=False, \
                                               layout=widgets.Layout(width='90%'))
        
        self.lightSheetCenter_w = widgets.IntSlider(min=-200, max=200, value=0, description='Center', \
                                    continuous_update=False, layout=widgets.Layout(width='90%'))
        
        self.lightSheetOffset_w = widgets.IntSlider(min=-300, max=300, value=0, description='Offset', \
                                      continuous_update=False, layout=widgets.Layout(width='90%'))
        
        self.lightSheetRotate_w = widgets.Checkbox(value=True, description='Flip90', disabled=False)
        
        if len(self.illumination) == 1:
            self.illumSide_w = widgets.RadioButtons(options=['Illum1'], disabled=True, 
                                                     layout=widgets.Layout(width='90%'))
            self.imagingArm_w = widgets.RadioButtons(options=['Illum1'], disabled=True, description='imagingArm', 
                                                     layout=widgets.Layout(width='90%'))
        else:
            self.illumSide_w = widgets.RadioButtons(options=['Illum1', 'Illum2'],disabled=False, 
                                                     layout=widgets.Layout(width='90%'))     
            self.imagingArm_w = widgets.RadioButtons(options=['Illum1', 'Illum2', 'Both'], \
                                                     disabled=False, description='imagingArm', 
                                                     layout=widgets.Layout(width='90%'))                      
                                  
        self.illum_button_w = widgets.Button(description='Illumination Off')
        
        illumination_w = interactive(self.interactive_illumination_update, \
                                     r=self.red_w, g=self.green_w, b=self.blue_w, \
                                     lwd=self.lightSheetWidth_w, lht=self.lightSheetHeight_w, lcent=self.lightSheetCenter_w,  \
                                     loffset=self.lightSheetOffset_w, d90=self.lightSheetRotate_w)
                                  
        switchIllumSide_w = interactive(self.interactive_illumination_switch, 
                                        illumSide=self.illumSide_w, layout=widgets.Layout(width='90%'))
        
        # Button responses
        self.illum_button_w.on_click(self.illumination_button_clicked)
        
        # Integrate
        illumination_control_w = widgets.VBox([self.illum_button_w, illumination_w, \
                                               widgets.HBox([widgets.VBox([switchIllumSide_w], layout=widgets.Layout(width='90%')), 
                                                             self.imagingArm_w],
                                                            layout=widgets.Layout(width='90%'))], \
                                    layout=widgets.Layout(width='45%', border = 'solid 1px'))
        return illumination_control_w
    
    def setup_realtimeScanning_experiment(self):
        
        self._scanningVolume_w = widgets.BoundedIntText(value=1, min=1, max=100000, step=1, \
                                             description='Scanning Volume #', \
                               layout=widgets.Layout(width='90%'), style = self._style)
        
        self._scanningDuration_w =widgets.BoundedFloatText(value=1, min=0, max=5000.0, step=0.1, \
                                                description='Total Duration (min)', \
                                                layout=widgets.Layout(width='90%'), style = self._style)
        
        self._scanningInterval_w = widgets.BoundedFloatText(value=1, min=0.1, max=5000.0, step=0.1, \
                                              description='Trial Inverval (min)', \
                                                layout=widgets.Layout(width='90%'), style = self._style)
        self._scanningRange_w = widgets.IntSlider(min=0, max=self.illumination[0].sc_W, value=100, \
                                        description='Scanning Range', continuous_update=False, \
                               layout=widgets.Layout(width='90%'), style = self._style)
        
        self._scanningStep_w = widgets.IntSlider(min=1, max=10, value=10, description='Scanning Step #', \
                                       continuous_update=False, layout=widgets.Layout(width='90%'), \
                                           style = self._style)
        
        scanning_begin_button_w = widgets.Button(description='Begin scanning', button_style = 'danger')

            
        scanning_begin_button_w.on_click(self.scanning_begin_button_clicked)
        
        realtimeScanning_control = widgets.VBox([widgets.VBox([self._scanningVolume_w, \
                                                                    self._scanningDuration_w, \
                                                               self._scanningInterval_w], \
                                                               layout=widgets.Layout(width='50%')), \
                                                 widgets.VBox([self._scanningRange_w, self._scanningStep_w, \
                                                               scanning_begin_button_w], \
                                                               layout=widgets.Layout(width='70%'))])
        return realtimeScanning_control

            
    def setup_wideField_experiment(self):
        self._totalFrames_w = widgets.BoundedIntText(value=1, min=1, max=100000, step=1, \
                                                 description='WideField', \
                       layout=widgets.Layout(width='90%'), style = self._style)

        wideField_begin_button_w = widgets.Button(description='Begin WideField', button_style = 'danger')
        
        
        wideField_begin_button_w.on_click(self.wideField_begin_button_clicked)
        wideField_control = widgets.VBox([self._totalFrames_w, wideField_begin_button_w], \
                                       layout=widgets.Layout(width='50%'))
        
        return wideField_control
    
    def setup_largeFOV_experiment(self):
        largeFOV_begin_button_w = widgets.Button(description='Begin Experiment', \
                                                 layout=widgets.Layout(width='auto', \
                                                grid_area = 'largeFOV_begin_button'), button_style = 'danger')
        largeFOV_begin_box = widgets.GridBox(children = [largeFOV_begin_button_w], 
                                            layout = widgets.Layout(width='100%',
                                            grid_template_rows = 'auto',
                                            grid_template_columns = '40% 40% 20%',
                                            grid_template_areas = '''
                                                ". . largeFOV_begin_button"
                                            '''))


        self._minX_w = widgets.BoundedFloatText(value=24.5, min=0, max=50, step=0.001, \
                                                description='Scan min X (mm)', \
                               layout=widgets.Layout(width='auto', grid_area = 'minX'), style = self._style)
        
        self._maxX_w = widgets.BoundedFloatText(value=25.5, min=0, max=50, step=0.001, \
                                                description='Scan max X (mm)', \
                               layout=widgets.Layout(width='auto', grid_area = 'maxX'), style = self._style)
        
        self._minY_w = widgets.BoundedFloatText(value=24.5, min=0, max=50, step=0.001, \
                                                description='Scan min Y (mm)', \
                               layout=widgets.Layout(width='auto', grid_area = 'minY'), style = self._style)
        
        self._maxY_w = widgets.BoundedFloatText(value=25.5, min=0, max=50, step=0.001, \
                                                description='Scan max Y (mm)', \
                               layout=widgets.Layout(width='auto', grid_area = 'maxY'), style = self._style)
        
        self._minZ_w = widgets.BoundedFloatText(value=24.5, min=0, max=50, step=0.001, \
                                                description='Scan min Z (mm)', \
                               layout=widgets.Layout(width='auto', grid_area = 'minZ'), style = self._style)
        
        self._maxZ_w = widgets.BoundedFloatText(value=25.5, min=0, max=50, step=0.001, \
                                                description='Scan max Z (mm)', \
                               layout=widgets.Layout(width='auto', grid_area = 'maxZ'), style = self._style)
        
        self._deltaZ_w = widgets.BoundedFloatText(value=0.1, min=0.001, max=10, step=0.001, \
                                            description='delta Z (mm)', \
                               layout=widgets.Layout(width='auto', grid_area = 'deltaZ'), style = self._style)
        
        self._overlap_w = widgets.BoundedFloatText(value=20, min=0, max=50, step=1, \
                                                   description='Overlap ratio (%)', \
                               layout=widgets.Layout(width='auto', grid_area = 'overlap'), style = self._style)

        self._cameraX_w = widgets.BoundedFloatText(value=0.86, min=0.001, max=5, step=0.001, \
                                            description='image size X (mm)', \
                               layout=widgets.Layout(width='auto', grid_area = 'cameraX'), style = self._style)
        
        self._cameraY_w = widgets.BoundedFloatText(value=0.45, min=0.001, max=5, step=0.001, \
                                                   description='image size Y (mm)', \
                               layout=widgets.Layout(width='auto', grid_area = 'cameraY'), style = self._style)
                                  
        interactFOV_w = interactive(self.interactive_fov_update, \
                                     minX = self._minX_w, minY = self._minY_w, minZ = self._minZ_w, \
                                     maxX = self._maxX_w, maxY = self._maxY_w, maxZ = self._maxZ_w, \
                                     deltaZ = self._deltaZ_w, overlap = self._overlap_w, \
                                     cameraX = self._cameraX_w, cameraY = self._cameraY_w,
                                     )
#         setFOV_box = widgets.GridBox(children = interactFOV_w, \
#                                             layout = widgets.Layout(width='100%', border = 'solid 1px',
#                                             grid_template_rows = 'auto auto',
#                                             grid_template_columns = '30% 30% 30%',
#                                             grid_template_areas = '''
#                                                 "minX minY minZ"
#                                                 "maxX maxY maxZ"
#                                                 "deltaZ overlap ."
#                                                 "cameraX cameraY ."
#                                             '''))
        setFOV_box = widgets.GridBox(children = [self._minX_w, self._minY_w, self._minZ_w, \
                                                 self._maxX_w, self._maxY_w, self._maxZ_w, \
                                                 self._deltaZ_w, self._overlap_w, self._cameraX_w, self._cameraY_w], \
                                            layout = widgets.Layout(width='100%', border = 'solid 1px',
                                            grid_template_rows = 'auto auto',
                                            grid_template_columns = '30% 30% 30%',
                                            grid_template_areas = '''
                                                "minX minY minZ"
                                                "maxX maxY maxZ"
                                                "deltaZ overlap ."
                                                "cameraX cameraY ."
                                            '''))

        addOffset_button_w = widgets.Button(description='Add Offset', \
                                            layout=widgets.Layout(width='auto', grid_area = 'addOffset'))
        
        delOffset_button_w = widgets.Button(description='Delete Offset', \
                                            layout=widgets.Layout(width='auto', grid_area = 'delOffset'))

        self._stageX_w = widgets.BoundedFloatText(value=25, min=0, max=50, step=0.001, \
                                                  description='Stage X (mm)', \
                               layout=widgets.Layout(width='auto', grid_area = 'stageX'), style = self._style)
        
        self._stageY_w = widgets.BoundedFloatText(value=25, min=0, max=50, step=0.001, \
                                                  description='Stage Y (mm)', \
                               layout=widgets.Layout(width='auto', grid_area = 'stageY'), style = self._style)
        
        self._stageZ_w = widgets.BoundedFloatText(value=25, min=0, max=50, step=0.001, \
                                                  description='Stage Z (mm)', \
                               layout=widgets.Layout(width='auto', grid_area = 'stageZ'), style = self._style)
        
        self._lsOffset1_w = widgets.BoundedIntText(value=0, min=-300, max=300, step=1, \
                                            description='Light Sheet 1 Offset', \
                               layout=widgets.Layout(width='auto', grid_area = 'lsOffset1'), style = self._style)
                                  
        self._lsOffset2_w = widgets.BoundedIntText(value=0, min=-300, max=300, step=1, \
                                            description='Light Sheet 2 Offset', \
                               layout=widgets.Layout(width='auto', grid_area = 'lsOffset2'), style = self._style)
                                  
        self._delRow_w = widgets.BoundedIntText(value=1, min=1, max=1, step=1, description='Delete row', \
                               layout=widgets.Layout(width='auto', grid_area = 'delRow'), style = self._style)
        
        setOffset_box = widgets.GridBox(children = [addOffset_button_w, delOffset_button_w, \
                                                    self._stageX_w, self._stageY_w, self._stageZ_w, \
                                                    self._lsOffset1_w, self._lsOffset2_w, self._delRow_w], 
                                            layout = widgets.Layout(width='100%', border = 'solid 1px',
                                            grid_template_rows = 'auto auto auto auto',
                                            grid_template_columns = '30% 30% 30%',
                                            grid_template_areas = '''
                                                "addOffset . . "
                                                "stageX stageY stageZ "
                                                "lsOffset1 lsOffset2 . "
                                                "delOffset delRow ."
                                            '''))
        
        
        self._sheet_w = ipysheet.sheet(rows = 30, columns = 5, column_headers = ['X', 'Y', 'Z', 'Offset1', 'Offset2'])

        self._alignment_array = []
        self._alignmentSheet_currRowID = 0
        
        largeFOV_begin_button_w.on_click(self.largeFOV_begin_button_clicked)
        addOffset_button_w.on_click(self.addOffset_button_clicked)
        delOffset_button_w.on_click(self.delOffset_button_clicked)
        
        largeFOV_control = widgets.VBox([largeFOV_begin_box, \
                                  setFOV_box, setOffset_box, \
                                  self._sheet_w], layout=widgets.Layout(width='90%'))
        
        return largeFOV_control
        
        
        
    def snapshot_button_clicked(self, b):
        PIL.Image.fromarray(self.camera.cam.GetNextImage(int(self.camera.exposure/1e3)). \
                            GetNDArray().copy()).save('./Snapshot-'+ \
                                                      time.strftime("%m-%d-%Y-%H-%M-%S", \
                                                                    time.localtime())+'.tif', 'tiff') 

    def frame_display_update(self):
        while self.camera.enable == True: #self.camera.stopFlag == False:
            time.sleep(0.5)
            f = io.BytesIO()
            self.camera.trigger_images()
            try:
                imageShow = self.camera.cam.GetNextImage(int(self.camera.exposure/1e3)).GetNDArray().copy()
                self.camera.currImage = imageShow
                imageShow[imageShow < self.dynamicRange_w.value[0]] = self.dynamicRange_w.value[0]
                imageShow[imageShow > self.dynamicRange_w.value[1]] = self.dynamicRange_w.value[1]

                imageShow = (imageShow - self.dynamicRange_w.value[0])/ \
                            (self.dynamicRange_w.value[1] - self.dynamicRange_w.value[0] + 1e-3)*255

                PIL.Image.fromarray(imageShow).convert('RGB').save(f, 'jpeg') 
                self.image_w.value = f.getvalue()
                self.image_w.width = min(imageShow.shape[1], 1000)
                self.image_w.height = min(imageShow.shape[0], 500)
            except:
                1
    
    def camera_button_clicked(self, button):
        self.save_parameters()
                                  
        if self.camera.enable == True:
            button.description='Waiting...'
            self.camera.enable = False
            self.camera.cam.EndAcquisition()
            button.description='Acquisition Off'
        
        elif self.camera.enable == False:
            button.description='Waiting...'
            self.camera.cam.BeginAcquisition()
            self.camera.enable = True

            stream_thread = threading.Thread(target=self.frame_display_update, args=())
            stream_thread.start()
            time.sleep(2)
            
            button.description='Acquisition On'
            
    def listen_camera_framerate(self, change):
        self.exposure_w.max = np.around(1/self.framerate_w.value*1000 - 50.5/3)


    def interactive_camera_update(self, framerate, exposure, gain):   
        self.camera.framerate = framerate
        self.camera.exposure = np.around(exposure*1000)
        self.camera.gain = gain
        self.camera.AcquisitionControl()
        self.camera.AnalogControl()    
        
        
    def illumination_button_clicked(self, button):
        self.save_parameters()
        if self.illumination[self.illumSide_w.index].enable == True:
            button.description='Waiting...'
            self.illumination[self.illumSide_w.index].enable = False
            self.illumination[self.illumSide_w.index].dark()
            
            time.sleep(1)
            button.description='Illumination Off'

        elif self.illumination[self.illumSide_w.index].enable == False:
            button.description='Waiting...'
            self.illumination[self.illumSide_w.index].enable = True
            self.illumination[self.illumSide_w.index].update()
            button.description='Illumination On'
            
    def interactive_illumination_update(self, r,g,b,lwd,lht,lcent,loffset,d90):
        color = "0x{0:02x}{1:02x}{2:02x}".format(max(0, min(r, 255)), \
                                                 max(0, min(g, 255)), max(0, min(b, 255)))

        self.illumination[self.illumSide_w.index].fg_color = int(color, 16)
        self.illumination[self.illumSide_w.index].lwd=lwd
        self.illumination[self.illumSide_w.index].lht=lht
        self.illumination[self.illumSide_w.index].lcent=lcent
        self.illumination[self.illumSide_w.index].loffset=loffset
        self.illumination[self.illumSide_w.index].d90=d90
        self.illumination[self.illumSide_w.index].update()

    def interactive_illumination_switch(self, illumSide):
        self.save_parameters()
#         print(illumSide)
        if self.illumination[1-self.illumSide_w.index].enable == True:
            self.illumination[self.illumSide_w.index].enable = True
            
            # Force update illumination values
            # TODO: make it elegant
            self.lightSheetOffset_w.value = self.illumination[self.illumSide_w.index].loffset
                                  
            self.illumination[self.illumSide_w.index].update()

        elif self.illumination[1-self.illumSide_w.index].enable == False:
            self.illumination[self.illumSide_w.index].enable = False
            self.illumination[self.illumSide_w.index].dark()
                                  
        self.illumination[1-self.illumSide_w.index].enable = False
        self.illumination[1-self.illumSide_w.index].dark()
                                  
       
                                  
#         self.illumination[0].enable = False
        
        
#         self.illumination[1].enable = False
#         self.illumination[1].dark()
           
#         self.illum_button_w.description='Illumination Off'
    def interactive_fov_update(self, minX, minY, minZ, maxX, maxY, maxZ, \
                                     deltaZ, overlap, cameraX, cameraY):
        xStep = (1-overlap/100)*cameraX
        x = np.arange(minX, maxX + xStep - 0.05, xStep)
        yStep = (1-overlap/100)*cameraY
        y = np.arange(minY, maxY + yStep - 0.05, yStep)
        z = np.arange(minZ, maxZ, deltaZ)
        
        self.status.value = 'Large FOV x-{0}, y-{1}, z-{2}'.format(len(x), len(y), len(z))                          
                                  
    def addOffset_button_clicked(self, button):
        lsOffset = np.array((self._stageX_w.value, self._stageY_w.value, \
                             self._stageZ_w.value, self._lsOffset1_w.value, self._lsOffset2_w.value))
        if len(self._alignment_array) == 0:
            self._alignment_array = lsOffset[np.newaxis, :]
        else:
            self._alignment_array = np.concatenate((self._alignment_array, lsOffset[np.newaxis, :]), axis = 0)
        ipysheet.row(self._alignmentSheet_currRowID, lsOffset)
        self._alignmentSheet_currRowID += 1
        self._delRow_w.max = self._alignmentSheet_currRowID
        
        self.save_parameters()

    def delOffset_button_clicked(self, button):
        if self._alignmentSheet_currRowID > 0:
            delRow = self._delRow_w.value - 1
            
            for i in range(delRow, self._alignmentSheet_currRowID -1):
                ipysheet.row(i, self._alignment_array[i+1,:])
                
            ipysheet.row(self._alignmentSheet_currRowID-1, ['','','','',''])
            self._alignment_array = np.delete(self._alignment_array, delRow, 0)    
            self._alignmentSheet_currRowID -= 1
            self._delRow_w.max = np.max([self._alignmentSheet_currRowID, 1])
        
        self.save_parameters()    
            
    def scanning_begin_button_clicked(self, button): 
        self.save_parameters()                          
        button.disabled = True
        button.description = 'In Experiment'   
        
        self.experiment.realtimeScanning_experiment_control(self._scanningVolume_w.value, \
                                            self._scanningDuration_w.value, self._scanningInterval_w.value, \
                                            self._scanningRange_w.value, self._scanningStep_w.value, \
                                            self.lightSheetOffset_w.value, self._outputPath_w.value)
        
        button.disabled = False
        button.description = 'Begin scanning'
        
        
    def wideField_begin_button_clicked(self, button):
        self.save_parameters()
        button.disabled = True
        button.description = 'In Experiment'
        
        self.experiment.widefield_experiment_control(self._outputPath_w.value, self._totalFrames_w.value)
        
        button.disabled = False
        button.description = 'WideField'
        
    def largeFOV_begin_button_clicked(self, button):
        self.save_parameters()
        button.disabled = True
        button.description = 'In Experiment'
        
        self.experiment.largeFOV_experiment_control( \
            self._minX_w.value, self._maxX_w.value, self._minY_w.value, self._maxY_w.value, \
            self._minZ_w.value, self._maxZ_w.value, \
            self._deltaZ_w.value, self._overlap_w.value, self._cameraX_w.value, self._cameraY_w.value, \
            self._alignment_array, self._outputPath_w.value)
        
        button.disabled = False
        button.description = 'Begin Experiment'

    def exit_button_clicked(self, button):
        try: 
            self.camera.cam.DeInit()

            print('Successfully exit. Please restart for using.')
            button.disabled = True
        except:
            print('Exit failed. Camera still in acquisition') 
    
    def save_metadata_file(self, path):
        metadata = pd.DataFrame({'FrameRateHz': self.framerate_w.value,
                      'ExposureSec': self.exposure_w.value,
                      'Gain': self.gain_w.value,
                      'Red': self.red_w.value,
                      'Green': self.green_w.value,
                      'Blue': self.blue_w.value,
                      'LightSheetWidth': self.lightSheetWidth_w.value,
                      'LightSheetHeight': self.lightSheetHeight_w.value,
                      'LightSheetCenter': self.lightSheetCenter_w.value,
                      'LightSheetOffset': self.lightSheetOffset_w.value,
                      'LightSheetRotate': self.lightSheetRotate_w.value, 
                      'ScanVolume': self._scanningVolume_w.value,
                      'ScanDuration': self._scanningDuration_w.value,
                      'ScanInterval': self._scanningInterval_w.value,
                      'ScanRange': self._scanningRange_w.value,
                      'ScanStep': self._scanningStep_w.value,
                      'FOVminX': self._minX_w.value,
                      'FOVmaxX': self._maxX_w.value,
                      'FOVminY': self._minY_w.value,
                      'FOVmaxY': self._maxY_w.value,
                      'FOVminZ': self._minZ_w.value,
                      'FOVmaxZ': self._maxZ_w.value,
                      'FOVdeltaZ': self._deltaZ_w.value,
                      'FOVoverlap': self._overlap_w.value,
                      'FOVcameraX': self._cameraX_w.value,
                      'FOVcameraY': self._cameraY_w.value,}, index = [0])
        metadata.to_csv(path + r'/metadata.csv')
        return 
        
    def save_parameters(self):
        with open('__parameters__.pkl', 'wb') as f:  # Python 3: open(..., 'wb')
            pickle.dump([self.framerate_w.value, self.exposure_w.value, self.gain_w.value] +
                        
                        [self.red_w.value, self.green_w.value, self.blue_w.value, \
                         self.lightSheetWidth_w.value, self.lightSheetHeight_w.value, self.lightSheetCenter_w.value, \
                         self.lightSheetOffset_w.value, self.lightSheetRotate_w.value] + 
                        
                        [ self._scanningVolume_w.value, self._scanningDuration_w.value, self._scanningInterval_w.value, \
                         self._scanningRange_w.value, self._scanningStep_w.value] + 
                        
                        [self._minX_w.value, self._maxX_w.value, self._minY_w.value, self._maxY_w.value, \
                         self._minZ_w.value, self._maxZ_w.value, self._deltaZ_w.value, self._overlap_w.value, \
                         self._alignment_array, self._alignmentSheet_currRowID], f, pickle.HIGHEST_PROTOCOL)    

    def load_parameters(self):
        try:                        
            with open('__parameters__.pkl', 'rb') as f:
                self.framerate_w.value, self.exposure_w.value, self.gain_w.value, \
                         self.red_w.value, self.green_w.value, self.blue_w.value, \
                         self.lightSheetWidth_w.value, self.lightSheetHeight_w.value, self.lightSheetCenter_w.value, \
                         self.lightSheetOffset_w.value, self.lightSheetRotate_w.value, \
                         self._scanningVolume_w.value, self._scanningDuration_w.value, self._scanningInterval_w.value, \
                         self._scanningRange_w.value, self._scanningStep_w.value, \
                         self._minX_w.value, self._maxX_w.value, self._minY_w.value, self._maxY_w.value, \
                         self._minZ_w.value, self._maxZ_w.value, self._deltaZ_w.value, self._overlap_w.value, \
                         self._alignment_array, self._alignmentSheet_currRowID = pickle.load(f)
            if self._alignmentSheet_currRowID > 0:
                for i in range(self._alignmentSheet_currRowID):
                    ipysheet.row(i, self._alignment_array[i,:])
        except:
            1
                                  
                                  
                                  
                                  