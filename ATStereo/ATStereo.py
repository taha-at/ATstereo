# ==============================================================================
# ATStereo Module
# Copyright (c) 2026 Abdelrahman Taha and Ahmed Abdelwahab
#
# PATENT NOTICE: The stereotactic frame geometry and associated methodologies
# implemented in this software are protected by patents.
#
# This software is licensed for academic and non-commercial research use ONLY.
# Commercial use, manufacturing, sale, or distribution is strictly prohibited
# without prior written permission from the authors.
# See the LICENSE file in the root of this repository for full terms.
#
# Portions of this software are derived from BrainStereo (MIT License).
# See LICENSE for the full BrainStereo copyright notice and terms.
# ==============================================================================

import os
import glob
import vtk,slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin
import math,functools
import numpy as np
from Resources.stereoLogic import stereoLogic
import qt

class ATStereo(ScriptedLoadableModule):

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "ATStereo" 
    self.parent.categories = ["Neurosurgery"] 
    self.parent.contributors = ["taha-at"]  
    self.parent.helpText = """
    <b>ATStereo</b><br>
    https://github.com/taha-at/ATstereo<br><br>
    <b>NOTICE:</b> The frame geometry is patented. This software is restricted to 
    academic and non-commercial research use only. Commercial use is prohibited.
    """

class ATStereoWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):

  def __init__(self, parent=None):
    ScriptedLoadableModuleWidget.__init__(self, parent)
    VTKObservationMixin.__init__(self)  
    self.logic = None

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)

    uiWidget = slicer.util.loadUI(self.resourcePath('UI/ATStereo.ui'))
    self.layout.addWidget(uiWidget)
    self.ui = slicer.util.childWidgetVariables(uiWidget)
    uiWidget.setMRMLScene(slicer.mrmlScene)

    self.ui.btn_choose_left_target_point.connect('clicked(bool)', self.on_add_target_point_left)
    self.ui.btn_choose_left_entry_point.connect('clicked(bool)', self.on_add_entry_point_left)
    self.ui.btn_choose_right_target_point.connect('clicked(bool)', self.on_add_target_point_right)
    self.ui.btn_choose_right_entry_point.connect('clicked(bool)', self.on_add_entry_point_right)

    self.ui.ctDataSelector.setMRMLScene(slicer.mrmlScene)
    self.ui.btn_clear.connect('clicked(bool)', self.reset)
    
    #transform - per-side arc angle and ring sliders
    self.ui.leftArcSlicer.valueChanged.connect(lambda: self.compute_arc_kinematics("left"))
    self.ui.leftRingSlicer.valueChanged.connect(lambda: self.compute_ring_kinematics("left"))
    self.ui.rightArcSlicer.valueChanged.connect(lambda: self.compute_arc_kinematics("right"))
    self.ui.rightRingSlicer.valueChanged.connect(lambda: self.compute_ring_kinematics("right"))
    self.ui.leftLocalXSlicer.valueChanged.connect(lambda: self.slider_transform("left"))
    self.ui.leftLocalYSlicer.valueChanged.connect(lambda: self.slider_transform("left"))
    self.ui.leftLocalZSlicer.valueChanged.connect(lambda: self.slider_transform("left"))
    self.ui.rightLocalXSlicer.valueChanged.connect(lambda: self.slider_transform("right"))
    self.ui.rightLocalYSlicer.valueChanged.connect(lambda: self.slider_transform("right"))
    self.ui.rightLocalZSlicer.valueChanged.connect(lambda: self.slider_transform("right"))  
    self.ui.visualizePlanBtn.connect('clicked(bool)', self.loadFrame)
    self.ui.visualizeFrameBtn.connect('clicked(bool)', self.visualFrame)
    self.ui.lockPlanBtn.connect('clicked(bool)', self.lockPlan)

    self.ui.showBtn.connect('clicked(bool)', self.volumeRender)
    self.ui.ctDataSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.onVolumeChanged)

    
    self.ui.newPlanBtn.connect('clicked(bool)', self.newPlan)

    self.ui.btn_pick_isocenters.connect('clicked(bool)', self.on_pick_isocenters)
    self.ui.btn_register_isocenters.connect('clicked(bool)', self.on_align_isocenters)

    self.ui.testBtn.connect('clicked(bool)', self.loadTestCt)

    self.ui.btn_importFiles.connect('clicked(bool)', self.onImportFiles)
    self.ui.btn_importFolder.connect('clicked(bool)', self.onImportFolder)

    

    self.defineiVar()


    self.sc=stereoLogic()
    self.sc.initTube()

    self.track=track()

    #self.initialize_coordinate_table()

    # Setup 3D view mouse move observer for data probe
    layoutManager = slicer.app.layoutManager()
    threeDWidget = layoutManager.threeDWidget(0)
    threeDView = threeDWidget.threeDView()
    self.interactor = threeDView.interactorStyle().GetInteractor()
    
    
    self.interactor.AddObserver('MouseMoveEvent', self.onMouseMove)
    self.onVolumeChanged()

  def onRegisterFrameClicked(self):
      """Triggered by the UI registerFrameButton to run tracking and register."""
      self.autodetect_frame_markers()
      slicer.util.showStatusMessage("Frame registered and RMSE logged!", 3000)

  def cleanup(self):
    self.removeObservers()
    self.clear_nodes()

  def clear_nodes(self):
    nodeList = [
        self.theoretical_fiducials,
        self.registration_markers,
        self.isocenterPoints,
        self.outputTransformNode,
        self.frameModel,
    ]
    for side in ["left", "right"]:
      if side in self.trajectory_targets:
          plan = self.trajectory_targets[side]
          nodeList.extend([
              plan.get("target"), plan.get("entry"), plan.get("tubeModel"),
              plan.get("supportModel"), plan.get("sliderModel"), plan.get("arcModel"),
              plan.get("boxModel"), plan.get("pathModel"), plan.get("axialModel"),
              plan.get("ATStereo_X_DriveTransform"), plan.get("ATStereo_Y_DriveTransform"), plan.get("ATStereo_Z_DriveTransform"),
              plan.get("ATStereo_RingMountTransform"), plan.get("ATStereo_TrajectoryGuideTransform"),
          ])
    for node in nodeList:
        if node is not None:
            slicer.mrmlScene.RemoveNode(node)
    self.defineiVar()

  def localToGlobal(self, side, x, y, z):
    if side == "left":
        gx = x
    else:
        gx = 200 - x
    gy = y
    gz = z
    return gx, gy, gz


  def defineiVar(self):
    self.theoretical_fiducials = None
    self.registration_markers = None
    self.isocenterPoints = None
    self.outputTransformNode = None
    self.frameModel = None
    self.sliderVis = False
    
    self.pointNodeObservers = []
    self.trajectory_targets = {
        "left": {
            "target": None,
            "entry": None,
            "tubeModel": None,

            "supportModel": None,
            "sliderModel": None,
            "arcModel": None,
            "boxModel": None,
            "pathModel": None,
            "axialModel": None,

            "ATStereo_X_DriveTransform": None,
            "ATStereo_Y_DriveTransform": None,
            "ATStereo_Z_DriveTransform": None,
            "ATStereo_RingMountTransform": None,
            "ATStereo_TrajectoryGuideTransform": None,

            "result": None,
            "offset": None,
            "basePosition": None,
            "isocenter": (-100.0, -60.0, 60.0),
        },
        "right": {
            "target": None,
            "entry": None,
            "tubeModel": None,

            "supportModel": None,
            "sliderModel": None,
            "arcModel": None,
            "boxModel": None,
            "pathModel": None,
            "axialModel": None,

            "ATStereo_X_DriveTransform": None,
            "ATStereo_Y_DriveTransform": None,
            "ATStereo_Z_DriveTransform": None,
            "ATStereo_RingMountTransform": None,
            "ATStereo_TrajectoryGuideTransform": None,

            "result": None,
            "offset": None,
            "basePosition": None,
            "isocenter": (100.0, -60.0, 60.0),
        }
    }

  def createPlanPointNode(self, nodeName, actorTag):
    node = slicer.mrmlScene.GetFirstNodeByName(nodeName)
    if node is None:
        node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", nodeName)
    node.RemoveAllControlPoints()
    node.GetDisplayNode().SetGlyphType(6)
    node.GetDisplayNode().SetGlyphSize(10)
    node.AddObserver(
        slicer.vtkMRMLMarkupsNode.PointModifiedEvent,
        functools.partial(self.on_plan_point_modified, actor=actorTag)
    )

    node.AddObserver(
        slicer.vtkMRMLMarkupsNode.PointEndInteractionEvent,
        self.observerEndMove
    )

    interactionNode = slicer.app.applicationLogic().GetInteractionNode()
    selectionNode = slicer.app.applicationLogic().GetSelectionNode()
    selectionNode.SetActivePlaceNodeID(node.GetID())
    interactionNode.SetPlaceModePersistence(0)
    interactionNode.SetCurrentInteractionMode(interactionNode.Place)
    return node
####################################################################################### for Rigist Frame    
  def initialize_coordinate_table(self):
        table=self.ui.planTable
        table.horizontalHeader().setSectionResizeMode(0, 1)
        table.horizontalHeader().setSectionResizeMode(1, 1)
        table.horizontalHeader().setSectionResizeMode(2, 1)
        table.horizontalHeader().setSectionResizeMode(3, 1)
        table.horizontalHeader().setSectionResizeMode(4, 2)
        table.horizontalHeader().setSectionResizeMode(5, 2)

  def render_theoretical_fiducials(self,points): # show standard points

    self.theoretical_fiducials = slicer.mrmlScene.GetFirstNodeByName("S")
    if (self.theoretical_fiducials is None):
      self.theoretical_fiducials = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "S")
    self.theoretical_fiducials.RemoveAllControlPoints()

    self.theoretical_fiducials.SetLocked(1)
     
    display_node = self.theoretical_fiducials.GetDisplayNode()
    display_node.SetGlyphType(5)
    display_node.SetTextScale(3)
    
    for i in points:
      self.theoretical_fiducials.AddFiducial(i[0],i[1],i[2])

    #rename 4 points
    name=["A  ","B  ","C  ","D  "]

    for i in range(4):
      self.theoretical_fiducials.SetNthControlPointLabel(i, name[i])

  def on_select_registration_markers(self):#select 4 points
    self.max2D()
    self.registration_markers= slicer.mrmlScene.GetFirstNodeByName("pointset")
    if(self.registration_markers is None):
        #slicer.app.layoutManager().threeDWidget(0).threeDView().lookFromAxis(3)
        self.registration_markers= slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "pointset")
        self.registration_markers.RemoveAllControlPoints()

    self.registration_markers.GetDisplayNode().SetGlyphType(2)
    
    self.registration_markers.RemoveAllObservers()
    self.registration_markers.AddObserver(
    slicer.vtkMRMLMarkupsNode.PointAddedEvent,
    functools.partial(self.on_four_point_added, actor="f"))

    interactionNode = slicer.app.applicationLogic().GetInteractionNode()
    selectionNode = slicer.app.applicationLogic().GetSelectionNode()
    selectionNode.SetActivePlaceNodeID(self.registration_markers.GetID())
    placeModePersistence = 1
    interactionNode.SetPlaceModePersistence(placeModePersistence)
    interactionNode.SetCurrentInteractionMode(interactionNode.Place)
   
    pointListDisplayNode = self.registration_markers.GetDisplayNode()
    pointListDisplayNode.SetSelectedColor(1,1,0)


  def max2D(self):
    layoutManager = slicer.app.layoutManager()
    layoutManager.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUpRedSliceView)
    redSliceCompositeNode = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceCompositeNodeRed")
    if redSliceCompositeNode:
        redSliceCompositeNode.SetBackgroundVolumeID(redSliceCompositeNode.GetBackgroundVolumeID())
  
  def identify_superior_fiducials(self):

    layoutManager = slicer.app.layoutManager()
    layoutManager.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutFourUpView)


  def comStandLocation(self):#print 4s tandard points position
    standardList=[]
    width=int(self.ui.widthEdit.text)
    height=int(self.ui.heightEdit.text)
    
    To1=[-width/2,height/2,height/2]
    To2=[width/2,height/2,height/2]
    To3=[width/2,-height/2,height/2]
    To4=[-width/2,-height/2,height/2]

    standardList.append(To1)
    standardList.append(To2)
    standardList.append(To3)
    standardList.append(To4)

    return standardList
  
  def sort_fiducials_anatomically(self, vtkpoints):
    # Retrieve points into a numpy array for vector operations
    pts = []
    for i in range(4):
        p = [0, 0, 0]
        vtkpoints.GetPoint(i, p)
        pts.append(np.array(p))

    # Calculate the spatial centroid of the 4 markers
    centroid = np.mean(pts, axis=0)
    
    # Classify each point into anatomical quadrants relative to the centroid
    # RAS Coordinate System: +X is Right, -X is Left. +Y is Anterior, -Y is Posterior.
    sorted_pts = [None] * 4
    for p in pts:
        is_right = p[0] > centroid[0]
        is_anterior = p[1] > centroid[1]

        if not is_right and is_anterior:
            sorted_pts[0] = p  # Left-Anterior
        elif is_right and is_anterior:
            sorted_pts[1] = p  # Right-Anterior
        elif is_right and not is_anterior:
            sorted_pts[2] = p  # Right-Posterior
        elif not is_right and not is_anterior:
            sorted_pts[3] = p  # Left-Posterior

    # Construct the ordered vtkPoints object and a native python list
    from_points_vtk = vtk.vtkPoints()
    sorted_pts_list = []
    
    for point in sorted_pts:
        if point is not None:
            pt_list = point.tolist()
            from_points_vtk.InsertNextPoint(pt_list)
            sorted_pts_list.append(pt_list)
        else:
            # Fallback in case of highly skewed marker placement (centroid classification fails)
            print("Warning: Spatial quadrant classification failed, reverting to linear sort.")
            pts.sort(key=lambda coord: (coord[0], coord[1]))
            sorted_pts_list = [fallback_pt.tolist() for fallback_pt in pts]
            for fallback_pt in pts:
                from_points_vtk.InsertNextPoint(fallback_pt.tolist())
            break

    return from_points_vtk, sorted_pts_list
  
  def autodetect_frame_markers(self):
      if self.registration_markers is None :
        slicer.util.messageBox("Please Select 4 Points")
        return
      n = self.registration_markers.GetNumberOfControlPoints()
      if n != 4:
        slicer.util.messageBox("Please Select 4 Points")
        return
      
      leksell = self.ui.ctDataSelector.currentNode()
      rass=self.track.startTrack(leksell,self.registration_markers)
      for i in range(4):
         self.registration_markers.SetNthControlPointPosition(i,rass[i])

      self.execute_rigid_registration()
         
  def execute_rigid_registration(self):#to register
    self.identify_superior_fiducials()

    stan=self.comStandLocation() 

    self.render_theoretical_fiducials(stan) 

    if self.registration_markers is None :
      slicer.util.messageBox("Please Select 4 Points")
      return
    n = self.registration_markers.GetNumberOfControlPoints()
    if n != 4:
      slicer.util.messageBox("Please Select 4 Points")
      return

    fromPointsOrdered = vtk.vtkPoints()
    toPointsOrdered = vtk.vtkPoints()

    for i in range(4):
      ras = vtk.vtkVector3d(0,0,0)
      self.registration_markers.GetNthControlPointPositionWorld(i,ras)
      fromPointsOrdered.InsertPoint(i, ras)
      toPointsOrdered.InsertPoint(i, stan[i])

    P = np.array([fromPointsOrdered.GetPoint(i) for i in range(4)]) 
    Q = np.array([toPointsOrdered.GetPoint(i) for i in range(4)])  
    #calculatedTransform =self.sc.kabsch(P,Q)

    landmarkTransform = vtk.vtkLandmarkTransform()
    landmarkTransform.SetSourceLandmarks(fromPointsOrdered)
    landmarkTransform.SetTargetLandmarks(toPointsOrdered)
    landmarkTransform.SetModeToRigidBody()
    landmarkTransform.Update()
    calculatedTransform = vtk.vtkMatrix4x4()
    landmarkTransform.GetMatrix(calculatedTransform)

    self.outputTransformNode = slicer.mrmlScene.GetFirstNodeByName("ATStereo_RegistrationTransform")
    if(self.outputTransformNode is None):
      self.outputTransformNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTransformNode", "ATStereo_RegistrationTransform")
    self.outputTransformNode.SetMatrixTransformToParent(calculatedTransform)
    self.registration_markers.SetAndObserveTransformNodeID(self.outputTransformNode.GetID())

    leksell = self.ui.ctDataSelector.currentNode()
    if leksell:
      leksell.SetAndObserveTransformNodeID(self.outputTransformNode.GetID())

    layoutManager = slicer.app.layoutManager()
    threeDWidget = layoutManager.threeDWidget(0) 
    threeDView = threeDWidget.threeDView()
    threeDView.resetFocalPoint() 
    slicer.util.resetSliceViews()
    
   
    total_squared_error = 0.0
    num_points = fromPointsOrdered.GetNumberOfPoints()

    for i in range(num_points):

        source_point = [0.0, 0.0, 0.0]
        fromPointsOrdered.GetPoint(i, source_point)
      
        transformed_point = [0.0, 0.0, 0.0]
        landmarkTransform.TransformPoint(source_point, transformed_point)
        
        target_point = [0.0, 0.0, 0.0]
        toPointsOrdered.GetPoint(i, target_point)
        
        squared_error = (
            (transformed_point[0] - target_point[0])**2 + 
            (transformed_point[1] - target_point[1])**2 + 
            (transformed_point[2] - target_point[2])**2 
        )
        
        total_squared_error += squared_error

    rms_error = round(math.sqrt(total_squared_error / num_points), 2)
    if rms_error>1.5:
       slicer.util.warningDisplay("The error is too large. Please re-register.", windowTitle="Warning")

    self.ui.errortext.setText(str(rms_error))

    # --- CSV LOGGING ---
    import csv, datetime, os
    csv_path = "/Users/abdelrahmantaha/Desktop/ATStereo_Phase1_RMSE.csv"
    file_exists = os.path.isfile(csv_path)
    try:
        with open(csv_path, mode='a', newline='') as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(["Timestamp", "RMSE", "Points_Used"])
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            writer.writerow([timestamp, rms_error, num_points])
            print(f"Logged RMSE: {rms_error} to {csv_path}")
    except Exception as e:
        print(f"Failed to log RMSE to CSV: {e}")
    # -------------------
  def on_pick_isocenters(self):
    self.max2D()
    self.isocenterPoints = slicer.mrmlScene.GetFirstNodeByName("Isocenters")
    if self.isocenterPoints is None:
        self.isocenterPoints = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "Isocenters")
        self.isocenterPoints.RemoveAllControlPoints()

    self.isocenterPoints.GetDisplayNode().SetGlyphType(6) # Star
    self.isocenterPoints.GetDisplayNode().SetSelectedColor(0, 1, 1) # Cyan

    interactionNode = slicer.app.applicationLogic().GetInteractionNode()
    selectionNode = slicer.app.applicationLogic().GetSelectionNode()
    selectionNode.SetActivePlaceNodeID(self.isocenterPoints.GetID())
    interactionNode.SetPlaceModePersistence(1)
    interactionNode.SetCurrentInteractionMode(interactionNode.Place)
    slicer.util.messageBox("Please place exactly 4 points: \n1. Left Isocenter\n2. Right Isocenter\n3. Left point at (0,0,120)\n4. Right point at (0,0,120)")

  def on_align_isocenters(self):
    if self.isocenterPoints is None or self.isocenterPoints.GetNumberOfControlPoints() < 4:
        slicer.util.messageBox("Please pick all 4 points first.")
        return

    # 1. Get the points picked by user
    p_left_iso = [0.0, 0.0, 0.0]
    p_right_iso = [0.0, 0.0, 0.0]
    p_left_120 = [0.0, 0.0, 0.0]
    p_right_120 = [0.0, 0.0, 0.0]
    
    self.isocenterPoints.GetNthControlPointPositionWorld(0, p_left_iso)
    self.isocenterPoints.GetNthControlPointPositionWorld(1, p_right_iso)
    self.isocenterPoints.GetNthControlPointPositionWorld(2, p_left_120)
    self.isocenterPoints.GetNthControlPointPositionWorld(3, p_right_120)

    fromPoints = vtk.vtkPoints()
    fromPoints.InsertNextPoint(p_left_iso)
    fromPoints.InsertNextPoint(p_right_iso)
    fromPoints.InsertNextPoint(p_left_120)
    fromPoints.InsertNextPoint(p_right_120)

    # 2. Define the theoretical target points
    iso_left = [-100.0, -60.0, 60.0]
    iso_right = [100.0, -60.0, 60.0]
    pt_left_120 = [-100.0, -60.0, -60.0]
    pt_right_120 = [100.0, -60.0, -60.0]

    toPoints = vtk.vtkPoints()
    toPoints.InsertNextPoint(iso_left)
    toPoints.InsertNextPoint(iso_right)
    toPoints.InsertNextPoint(pt_left_120)
    toPoints.InsertNextPoint(pt_right_120)

    # 3. Compute Rigid Transform
    landmarkTransform = vtk.vtkLandmarkTransform()
    landmarkTransform.SetSourceLandmarks(fromPoints)
    landmarkTransform.SetTargetLandmarks(toPoints)
    landmarkTransform.SetModeToRigidBody()
    landmarkTransform.Update()
    
    calculatedTransform = vtk.vtkMatrix4x4()
    landmarkTransform.GetMatrix(calculatedTransform)

    # 4. Apply to output node
    self.outputTransformNode = slicer.mrmlScene.GetFirstNodeByName("ATStereo_RegistrationTransform")
    if self.outputTransformNode is None:
      self.outputTransformNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTransformNode", "ATStereo_RegistrationTransform")
    self.outputTransformNode.SetMatrixTransformToParent(calculatedTransform)

    self.isocenterPoints.SetAndObserveTransformNodeID(self.outputTransformNode.GetID())

    leksell = self.ui.ctDataSelector.currentNode()
    if leksell:
      leksell.SetAndObserveTransformNodeID(self.outputTransformNode.GetID())

    # 5. Compute and Display RMS Error
    total_squared_error = 0.0
    num_points = fromPoints.GetNumberOfPoints()

    for i in range(num_points):
        source_point = [0.0, 0.0, 0.0]
        fromPoints.GetPoint(i, source_point)
      
        transformed_point = [0.0, 0.0, 0.0]
        landmarkTransform.TransformPoint(source_point, transformed_point)
        
        target_point = [0.0, 0.0, 0.0]
        toPoints.GetPoint(i, target_point)
        
        squared_error = (
            (transformed_point[0] - target_point[0])**2 + 
            (transformed_point[1] - target_point[1])**2 + 
            (transformed_point[2] - target_point[2])**2 
        )
        total_squared_error += squared_error

    rms_error = round(math.sqrt(total_squared_error / num_points), 2)
    self.ui.errortext.setText(str(rms_error))
    # --- CSV LOGGING ---
    import csv, datetime, os
    csv_path = "/Users/abdelrahmantaha/Desktop/ATStereo_Phase1_RMSE.csv"
    file_exists = os.path.isfile(csv_path)
    try:
        with open(csv_path, mode='a', newline='') as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(["Timestamp", "RMSE", "Points_Used"])
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            writer.writerow([timestamp, rms_error, num_points])
            print(f"Logged Isocenter RMSE: {rms_error} to {csv_path}")
    except Exception as e:
        print(f"Failed to log RMSE to CSV: {e}")
    # -------------------
    
    # 6. Reset views
    layoutManager = slicer.app.layoutManager()
    threeDWidget = layoutManager.threeDWidget(0) 
    threeDView = threeDWidget.threeDView()
    threeDView.resetFocalPoint() 
    slicer.util.resetSliceViews()
    
    if rms_error > 2.0:
        slicer.util.warningDisplay(f"The alignment error is very large (RMSE = {rms_error} mm). \nMake sure you picked the points in the EXACT order: \n1. Left Isocenter\n2. Right Isocenter\n3. Left (0,0,120)\n4. Right (0,0,120).", windowTitle="High Error Warning")
    else:
        slicer.util.messageBox(f"Alignment complete! (RMSE = {rms_error} mm)")

  def hidePoints(self):
    node1= self.registration_markers
    node2= self.theoretical_fiducials
    if node1 and node2:
      node1.GetDisplayNode().SetVisibility(0)
      node2.GetDisplayNode().SetVisibility(0)

####################################################################################### for target and entry

  def on_add_target_point_left(self):
      self.hidePoints()
      self.trajectory_targets["left"]["target"] = self.createPlanPointNode("targetPointLeft", "t_left")
    

  def on_add_entry_point_left(self):
      self.trajectory_targets["left"]["entry"] = self.createPlanPointNode("entryPointLeft", "e_left")

  def on_add_target_point_right(self):
      self.hidePoints()
      self.trajectory_targets["right"]["target"] = self.createPlanPointNode("targetPointRight", "t_right")

  def on_add_entry_point_right(self):
      self.trajectory_targets["right"]["entry"] = self.createPlanPointNode("entryPointRight", "e_right")

  
  def newPlan(self):
    for side in ["left", "right"]:
        tube = self.trajectory_targets[side]["tubeModel"]
        if tube is not None:
            self.sc.addPlan(tube)


####################################################################################### Observer 
  def on_plan_point_modified(self, caller, event, actor=None):
    if actor in ["t_left", "e_left"]:
        self.updatePlan("left")
    elif actor in ["t_right", "e_right"]:
        self.updatePlan("right")

  def updatePlan(self, side):
    self.updatePlanResult(side)
    self.updatePlanTube(side)
    self.applyPlanTransform(side)
    self.checkTrajectorySeparation()

  def updatePlanResult(self, side):
    plan = self.trajectory_targets[side]
    target = plan["target"]
    entry = plan["entry"]

    if target is None or target.GetNumberOfControlPoints() == 0:
        return

    label_target = f"{side} - target"
    target.SetNthControlPointLabel(0, label_target)

    target_ras = vtk.vtkVector3d(0, 0, 0)
    target.GetNthControlPointPositionWorld(0, target_ras)

    if entry is not None and entry.GetNumberOfControlPoints() > 0:
        label_entry = f"{side} - entry"
        entry.SetNthControlPointLabel(0, label_entry)

        entry_ras = vtk.vtkVector3d(0, 0, 0)
        entry.GetNthControlPointPositionWorld(0, entry_ras)

        distance = np.linalg.norm(np.array([
            entry_ras[0] - target_ras[0],
            entry_ras[1] - target_ras[1],
            entry_ras[2] - target_ras[2]
        ]))

        if side == "left":
            self.ui.distanceText.setText(str(round(distance, 2)))

        plan["result"] = self.computeDualArcResult(side, target_ras, entry_ras)
    else:
        plan["result"] = self.computeDualArcResult(side, target_ras, None)

    result = plan["result"]
    if result is None:
        return

    warnings = result.get("warnings", [])
    if warnings:
        warn_text = f"LIMIT EXCEEDED ({side.upper()}): " + ", ".join(warnings)
        print(warn_text)
        slicer.util.showStatusMessage(warn_text, 3000)
    else:
        slicer.util.showStatusMessage("", 0)

    if side == "left":
        self.ui.left_final_x.setText(str(result["x"]))
        self.ui.left_final_y.setText(str(result["y"]))
        self.ui.left_final_z.setText(str(result["z"]))
        self.ui.leftArc.setText(str(result["arc"]))
        self.ui.leftRing.setText(str(result["ring"]))

        self.ui.leftLocalXSlicer.blockSignals(True)
        self.ui.leftLocalYSlicer.blockSignals(True)
        self.ui.leftLocalZSlicer.blockSignals(True)
        self.ui.leftRingSlicer.blockSignals(True)
        self.ui.leftArcSlicer.blockSignals(True)

        self.ui.leftLocalXSlicer.value = result["x"]
        self.ui.leftLocalYSlicer.value = result["y"]
        self.ui.leftLocalZSlicer.value = result["z"]
        self.ui.leftRingSlicer.value = result["ring"]
        self.ui.leftArcSlicer.value = result["arc"]

        self.ui.leftLocalXSlicer.blockSignals(False)
        self.ui.leftLocalYSlicer.blockSignals(False)
        self.ui.leftLocalZSlicer.blockSignals(False)
        self.ui.leftRingSlicer.blockSignals(False)
        self.ui.leftArcSlicer.blockSignals(False)
    else:
        self.ui.right_final_x.setText(str(result["x"]))
        self.ui.right_final_y.setText(str(result["y"]))
        self.ui.right_final_z.setText(str(result["z"]))
        self.ui.rightArc.setText(str(result["arc"]))
        self.ui.rightRing.setText(str(result["ring"]))

        self.ui.rightLocalXSlicer.blockSignals(True)
        self.ui.rightLocalYSlicer.blockSignals(True)
        self.ui.rightLocalZSlicer.blockSignals(True)
        self.ui.rightRingSlicer.blockSignals(True)
        self.ui.rightArcSlicer.blockSignals(True)

        self.ui.rightLocalXSlicer.value = result["x"]
        self.ui.rightLocalYSlicer.value = result["y"]
        self.ui.rightLocalZSlicer.value = result["z"]
        self.ui.rightRingSlicer.value = result["ring"]
        self.ui.rightArcSlicer.value = result["arc"]

        self.ui.rightLocalXSlicer.blockSignals(False)
        self.ui.rightLocalYSlicer.blockSignals(False)
        self.ui.rightLocalZSlicer.blockSignals(False)
        self.ui.rightRingSlicer.blockSignals(False)
        self.ui.rightArcSlicer.blockSignals(False)

  def computeDualArcResult(self, side, target_ras, entry_ras=None):
    
    iso = self.trajectory_targets[side]["isocenter"]
    if entry_ras is None:
        self.setupDataProbecoordinates(target_ras[0], target_ras[1], target_ras[2])
    else:
        self.setupDataProbecoordinates(entry_ras[0], entry_ras[1], entry_ras[2])
        
    t = np.array([
        target_ras[0] - iso[0],
        target_ras[1] - iso[1],
        target_ras[2] - iso[2]
    ], dtype=float)
    

    if side == "left":
        local_x = t[0]
    else:
        local_x = -t[0]

    local_y = t[1]
    local_z = t[2]

    LIMITS = {
        "x": {"min": 0, "max": 100},
        "y": {"min": -60, "max": 120},
        "z": {"min": 0, "max": 120},
        "arc": {"min": -10, "max": 60},
        "ring": {"min": 0, "max": 360}
    }
    warnings = []

    def check_and_clamp(val, param):
        if val < LIMITS[param]["min"] or val > LIMITS[param]["max"]:
            warnings.append(f"{param.capitalize()} out of bounds: {val:.1f}")
        return max(LIMITS[param]["min"], min(LIMITS[param]["max"], val))

    local_x = check_and_clamp(local_x, "x")
    local_y = check_and_clamp(local_y, "y")
    local_z = check_and_clamp(-local_z, "z")

    if entry_ras is not None:
        e = np.array([
            entry_ras[0] - iso[0],
            entry_ras[1] - iso[1],
            entry_ras[2] - iso[2]
        ], dtype=float)
        # Direction vector from entry to target (Globocentric convention)
        a = [t[i] - e[i] for i in range(3)]
        A = math.sqrt(sum(v * v for v in a))

        if A < 1e-6:
            return None

        # Arc angle: from X axis (Globocentric)
        if side == "right":
            val_arc = max(-1.0, min(1.0, -a[0] / A))
        else:
            val_arc = max(-1.0, min(1.0, a[0] / A))
        arc = 90.0 - math.degrees(math.acos(val_arc))
        arc = check_and_clamp(arc, "arc")
                
        diffZ = abs(t[2]) - abs(e[2])
        # Ring angle: computed from Y/Z plane with quadrant logic (Globocentric)
        if abs(a[1]) < 1e-12:
            alpha_y = 90.0
        else:
            alpha_y = math.degrees(math.atan(abs(a[2]) / abs(a[1])))

        if a[2] == 0:
            if a[1] > 0:
                ring = 270.0
            else:
                ring = 90.0
        elif a[1] == 0:
            if diffZ > 0:
                ring = 0.0
            else:
                ring = 180.0
        elif diffZ > 0:
            if a[1] > 0:
                ring = 270.0 + alpha_y
            else:
                ring = 90.0 - alpha_y
        elif diffZ < 0:
            if a[1] < 0:
                ring = 90.0 + alpha_y 
            else:
                ring = 270.0 - alpha_y
        else:
            ring = 0.0
        
        if side == "left":
            local_x = check_and_clamp(t[0], "x")
        else:
            local_x = check_and_clamp(-t[0], "x")
            
        local_z = check_and_clamp(-t[2], "z")
        ring = check_and_clamp(ring, "ring")
    else:
        arc = 0.0
        ring = 0.0

    return {
        "x": round(local_x, 2),
        "y": round(local_y, 2),
        "z": round(local_z, 2),
        "arc": round(arc, 2),
        "ring": round(ring, 2),
        "warnings": warnings
    }


  def checkTrajectorySeparation(self, minDistanceMm=5.0):
    left = self.trajectory_targets["left"]
    right = self.trajectory_targets["right"]

    if not left["entry"] or not left["target"] or not right["entry"] or not right["target"]:
        return
    if left["entry"].GetNumberOfControlPoints() == 0 or left["target"].GetNumberOfControlPoints() == 0:
        return
    if right["entry"].GetNumberOfControlPoints() == 0 or right["target"].GetNumberOfControlPoints() == 0:
        return

    le = [0, 0, 0]
    lt = [0, 0, 0]
    re = [0, 0, 0]
    rt = [0, 0, 0]

    left["entry"].GetNthControlPointPositionWorld(0, le)
    left["target"].GetNthControlPointPositionWorld(0, lt)
    right["entry"].GetNthControlPointPositionWorld(0, re)
    right["target"].GetNthControlPointPositionWorld(0, rt)

    d_entry = np.linalg.norm(np.array(le) - np.array(re))
    d_target = np.linalg.norm(np.array(lt) - np.array(rt))

    if d_entry < minDistanceMm or d_target < minDistanceMm:
        slicer.util.warningDisplay("Warning: left and right trajectories are very close.")

        
    ##observe 4 points
  
  def observeFourPoints(self):# 
      self.registration_markers = slicer.mrmlScene.GetFirstNodeByName("pointset")
      node=self.registration_markers
      if node:
        n = node.GetNumberOfControlPoints()
        interactionNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLInteractionNode")
        if n > 4:
          interactionNode = slicer.app.applicationLogic().GetInteractionNode()
          interactionNode.SetCurrentInteractionMode(interactionNode.ViewTransform)

          nodeVtkPoints=vtk.vtkPoints()
          for i in range(4):
            ras = vtk.vtkVector3d(0,0,0)
            node.GetNthControlPointPositionWorld(i,ras)
            nodeVtkPoints.InsertPoint(i, ras)
          _,nodeListPoints=self.sort_fiducials_anatomically(nodeVtkPoints)
          node.RemoveAllControlPoints()
          node.GetDisplayNode().SetGlyphType(2)
          name=["    a","    b","    c","    d"]
          for i in range(4):
            node.AddControlPointWorld(nodeListPoints[i])
            node.SetNthControlPointLabel(i,name[i])

  def on_four_point_added(self, caller, event, actor=None):
    self.observeFourPoints()

  def updatePlanTube(self, side):
    plan = self.trajectory_targets[side]

    if not plan["target"] or not plan["entry"]:
        return
    if plan["target"].GetNumberOfControlPoints() == 0 or plan["entry"].GetNumberOfControlPoints() == 0:
        return

    p1 = [0, 0, 0]
    p2 = [0, 0, 0]
    plan["target"].GetNthControlPointPositionWorld(0, p1)
    plan["entry"].GetNthControlPointPositionWorld(0, p2)

    tube = self.sc.updateTube(p1, p2)

    if plan["tubeModel"] is None:
        plan["tubeModel"] = slicer.modules.models.logic().AddModel(tube.GetOutputPort())
        plan["tubeModel"].SetName(f"tubeModel_{side}")
    else:
        plan["tubeModel"].SetPolyDataConnection(tube.GetOutputPort())

    if side == "left":
        plan["tubeModel"].GetDisplayNode().SetColor(1, 0, 0)
    else:
        plan["tubeModel"].GetDisplayNode().SetColor(0, 0, 1)

    plan["tubeModel"].GetDisplayNode().SetVisibility2D(True)
    plan["tubeModel"].GetDisplayNode().SetOpacity(0.5)


  def observerStartMove(self, caller, event):
    for side in ["left", "right"]:
        tube = self.trajectory_targets[side]["tubeModel"]
        if tube is not None:
            tube.GetDisplayNode().SetVisibility(0)
 
  def observerEndMove(self, caller, event):
    for side in ["left", "right"]:
        tube = self.trajectory_targets[side]["tubeModel"]
        if tube is not None:
            tube.GetDisplayNode().SetVisibility(1)
    self.syncPlan()
  
  
  def reset(self):
    self.clear_nodes()

    self.ui.leftArc.setText("0")
    self.ui.leftRing.setText("0")
    self.ui.rightArc.setText("0")
    self.ui.rightRing.setText("0")

    self.ui.left_final_x.setText("0")
    self.ui.left_final_y.setText("0")  
    self.ui.left_final_z.setText("0")

    self.ui.right_final_x.setText("0")
    self.ui.right_final_y.setText("0")
    self.ui.right_final_z.setText("0")

    self.ui.errortext.setText("0")
    self.ui.distanceText.setText("0")

    self.ui.leftArcSlicer.setValue(0)
    self.ui.rightArcSlicer.setValue(0)
    self.ui.depthEdit.setText("120")
    
    # Block signals for BOTH sides
    self.ui.rightLocalXSlicer.blockSignals(True)
    self.ui.rightLocalYSlicer.blockSignals(True)
    self.ui.rightLocalZSlicer.blockSignals(True)
    self.ui.rightRingSlicer.blockSignals(True)
    self.ui.rightArcSlicer.blockSignals(True)

    self.ui.leftLocalXSlicer.blockSignals(True)
    self.ui.leftLocalYSlicer.blockSignals(True)
    self.ui.leftLocalZSlicer.blockSignals(True)
    self.ui.leftRingSlicer.blockSignals(True)
    self.ui.leftArcSlicer.blockSignals(True)

    # Set values to 0
    self.ui.rightLocalXSlicer.value = 0
    self.ui.rightLocalYSlicer.value = 0
    self.ui.rightLocalZSlicer.value = 0
    self.ui.rightRingSlicer.value = 0
    self.ui.rightArcSlicer.value = 0

    self.ui.leftLocalXSlicer.value = 0
    self.ui.leftLocalYSlicer.value = 0
    self.ui.leftLocalZSlicer.value = 0
    self.ui.leftRingSlicer.value = 0
    self.ui.leftArcSlicer.value = 0

    # Unblock signals for BOTH sides
    self.ui.rightLocalXSlicer.blockSignals(False)
    self.ui.rightLocalYSlicer.blockSignals(False)
    self.ui.rightLocalZSlicer.blockSignals(False)
    self.ui.rightRingSlicer.blockSignals(False)
    self.ui.rightArcSlicer.blockSignals(False)

    self.ui.leftLocalXSlicer.blockSignals(False)
    self.ui.leftLocalYSlicer.blockSignals(False)
    self.ui.leftLocalZSlicer.blockSignals(False)
    self.ui.leftRingSlicer.blockSignals(False)
    self.ui.leftArcSlicer.blockSignals(False)



#######################################################################################  For Simulation
  def loadFrame(self):
    if self.frameModel is None:
        self.frameModel = slicer.util.loadModel(self.resourcePath('frame/Frame.stl'))
        self.frameModel.GetDisplayNode().SetColor(1, 238/255, 0)

    self.loadPlanModels("left", "Supportleft.stl", "Sliderleft.stl", "ArcLeft.stl", "Boxleft.stl", "Pathleft.stl", "Axialleft.stl")
    self.loadPlanModels("right", "Supportright.stl", "Sliderright.stl", "ArcRight.stl", "Boxright.stl", "Pathright.stl", "Axialright.stl")

    self.syncPlan()

    self.applyPlanTransform("left")
    self.applyPlanTransform("right")

  def loadPlanModels(self, side, supportFile, sliderFile, arcFile, boxFile, pathFile, axialFile):
      plan = self.trajectory_targets[side]

      if plan["supportModel"] is None:
          plan["supportModel"] = slicer.util.loadModel(self.resourcePath(f'frame/{supportFile}'))
          plan["supportModel"].SetName(f"Support_{side}")

      if plan["sliderModel"] is None:
          plan["sliderModel"] = slicer.util.loadModel(self.resourcePath(f'frame/{sliderFile}'))
          plan["sliderModel"].SetName(f"Slider_{side}")

      if plan["arcModel"] is None:
          plan["arcModel"] = slicer.util.loadModel(self.resourcePath(f'frame/{arcFile}'))
          plan["arcModel"].SetName(f"Arc_{side}")

      if plan["boxModel"] is None:
          plan["boxModel"] = slicer.util.loadModel(self.resourcePath(f'frame/{boxFile}'))
          plan["boxModel"].SetName(f"Box_{side}")

      if plan["pathModel"] is None:
          plan["pathModel"] = slicer.util.loadModel(self.resourcePath(f'frame/{pathFile}'))
          plan["pathModel"].SetName(f"Path_{side}")

      if plan["axialModel"] is None:
          plan["axialModel"] = slicer.util.loadModel(self.resourcePath(f'frame/{axialFile}'))
          plan["axialModel"].SetName(f"Axial_{side}")

      if plan["ATStereo_X_DriveTransform"] is None:
          plan["ATStereo_X_DriveTransform"] = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTransformNode", f"supportTran_{side}")

      if plan["ATStereo_Y_DriveTransform"] is None:
          plan["ATStereo_Y_DriveTransform"] = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTransformNode", f"sliderTran_{side}")

      if plan["ATStereo_Z_DriveTransform"] is None:
          plan["ATStereo_Z_DriveTransform"] = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTransformNode", f"arcTran_{side}")

      if plan["ATStereo_RingMountTransform"] is None:
          plan["ATStereo_RingMountTransform"] = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTransformNode", f"boxTran_{side}")

      if plan["ATStereo_TrajectoryGuideTransform"] is None:
          plan["ATStereo_TrajectoryGuideTransform"] = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTransformNode", f"pathTran_{side}")

      plan["supportModel"].SetAndObserveTransformNodeID(plan["ATStereo_X_DriveTransform"].GetID())
      plan["sliderModel"].SetAndObserveTransformNodeID(plan["ATStereo_Y_DriveTransform"].GetID())
      plan["arcModel"].SetAndObserveTransformNodeID(plan["ATStereo_Z_DriveTransform"].GetID())
      plan["boxModel"].SetAndObserveTransformNodeID(plan["ATStereo_RingMountTransform"].GetID())
      plan["pathModel"].SetAndObserveTransformNodeID(plan["ATStereo_TrajectoryGuideTransform"].GetID())
      # plan["axialModel"].SetAndObserveTransformNodeID(plan["ATStereo_RingMountTransform"].GetID())  # Commented out to keep axial fixed in place

      # hierarchy
      plan["ATStereo_Y_DriveTransform"].SetAndObserveTransformNodeID(plan["ATStereo_X_DriveTransform"].GetID())
      plan["ATStereo_Z_DriveTransform"].SetAndObserveTransformNodeID(plan["ATStereo_Y_DriveTransform"].GetID())
      plan["ATStereo_RingMountTransform"].SetAndObserveTransformNodeID(plan["ATStereo_Z_DriveTransform"].GetID())
      plan["ATStereo_TrajectoryGuideTransform"].SetAndObserveTransformNodeID(plan["ATStereo_RingMountTransform"].GetID())

  def onImportFiles(self):
    """Open a file dialog to select one or more NIfTI files to load."""
    parent = slicer.util.mainWindow()
    filePaths = qt.QFileDialog.getOpenFileNames(
        parent,
        "Select NIfTI Files",
        os.path.expanduser("~"),
        "NIfTI Files (*.nii *.nii.gz);;All Files (*)"
    )
    if filePaths:
        self._loadNiftiFiles(filePaths)

  def onImportFolder(self):
    """Open a folder dialog and recursively scan for NIfTI files to load."""
    parent = slicer.util.mainWindow()
    folderPath = qt.QFileDialog.getExistingDirectory(
        parent,
        "Select Folder Containing NIfTI Files",
        os.path.expanduser("~"),
        qt.QFileDialog.ShowDirsOnly
    )
    if folderPath and folderPath != ".":
        niftiFiles = sorted(
            glob.glob(os.path.join(folderPath, "**", "*.nii"), recursive=True)
            + glob.glob(os.path.join(folderPath, "**", "*.nii.gz"), recursive=True)
        )
        if not niftiFiles:
            slicer.util.messageBox("No NIfTI files (.nii, .nii.gz) found in the selected folder.")
            return
        self._loadNiftiFiles(niftiFiles)

  def _loadNiftiFiles(self, filePaths):
    """Load a list of NIfTI file paths into the scene.

    Skips files already loaded (by filename), shows a wait cursor during loading,
    updates the status label, and auto-selects the last loaded volume.
    """
    slicer.app.setOverrideCursor(qt.Qt.WaitCursor)
    try:
        # Get names of volumes already in the scene for duplicate detection
        existingNames = set()
        for node in slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode"):
            existingNames.add(node.GetName())
        for node in slicer.util.getNodesByClass("vtkMRMLVectorVolumeNode"):
            existingNames.add(node.GetName())

        loadedCount = 0
        skippedCount = 0
        lastNode = None

        for filePath in filePaths:
            baseName = os.path.basename(filePath).split(".nii")[0]
            if baseName in existingNames:
                skippedCount += 1
                continue
            try:
                node = slicer.util.loadVolume(filePath)
                if node:
                    slicer.modules.volumes.logic().CenterVolume(node)
                    lastNode = node
                    loadedCount += 1
                    existingNames.add(node.GetName())
            except Exception as e:
                print(f"Failed to load {filePath}: {e}")

        # Update status label
        statusParts = []
        if loadedCount > 0:
            statusParts.append(f"Loaded {loadedCount} volume(s)")
        if skippedCount > 0:
            statusParts.append(f"Skipped {skippedCount} duplicate(s)")
        if not statusParts:
            statusParts.append("No new files to load")
        self.ui.importStatusLabel.setText(" | ".join(statusParts))

        # Auto-select the last loaded volume in ctDataSelector
        if lastNode is not None:
            self.ui.ctDataSelector.setCurrentNode(lastNode)

    finally:
        slicer.app.restoreOverrideCursor()

  def loadTestCt(self):
    """This function loads the test CT data, auto-downloading it if missing."""
    import os
    import urllib.request
    
    ctPath = self.resourcePath('ctData/Test.nrrd')
    
    # If file doesn't exist, or is just a small LFS text pointer (< 1 MB)
    if not os.path.exists(ctPath) or os.path.getsize(ctPath) < 1000000:
        slicer.util.showStatusMessage("Downloading Test CT Scan (~82 MB)... Please wait, Slicer will freeze during download.", 10000)
        slicer.app.processEvents() # Force the UI to show the message
        
        url = "https://github.com/taha-at/ATstereo/raw/main/ATStereo/Resources/ctData/Test.nrrd"
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(ctPath), exist_ok=True)
            urllib.request.urlretrieve(url, ctPath)
            slicer.util.showStatusMessage("Download complete!", 3000)
        except Exception as e:
            slicer.util.errorDisplay(f"Failed to download Test CT. \nError: {e}\n\nYou can manually download it from:\n{url}")
            return

    node = slicer.util.loadVolume(ctPath)
    if node:
        slicer.modules.volumes.logic().CenterVolume(node)
        self.ui.ctDataSelector.setCurrentNode(node)

  def syncPlan(self):
    """This function syncs the plan between the left and right trajectories."""
    for side in ["left", "right"]:
        self.applyPlanTransform(side)

  def _arcPivotTransform(self, side, arc_value):
    """Create a transform that rotates around the side's isocenter by arc_value degrees (Y axis)."""
    px, py, pz = self.trajectory_targets[side]["isocenter"]
    t = vtk.vtkTransform()
    t.Translate(px, py, pz)
    t.RotateY(arc_value)
    t.Translate(-px, -py, -pz)
    return t

  def _ringPivotTransform(self, side, ring_value):
    """Create a transform that rotates around the side's isocenter by ring_value degrees (X axis)."""
    px, py, pz = self.trajectory_targets[side]["isocenter"]
    t = vtk.vtkTransform()
    t.Translate(px, py, pz)
    t.RotateX(360-ring_value)
    t.Translate(-px, -py, -pz)
    return t

  def compute_arc_kinematics(self, side):
    """This function computes the arc kinematics for the trajectory targets."""
    plan = self.trajectory_targets[side]
    if plan["ATStereo_RingMountTransform"] is None:
        return

    if side == "left":
        arc_value = -self.ui.leftArcSlicer.value
    else:
        arc_value = self.ui.rightArcSlicer.value

    boxTransform = self._arcPivotTransform(side, arc_value)
    plan["ATStereo_RingMountTransform"].SetMatrixTransformToParent(boxTransform.GetMatrix())

  def compute_ring_kinematics(self, side):
    """This function computes the ring kinematics for the trajectory targets."""
    plan = self.trajectory_targets[side]
    if plan["ATStereo_Z_DriveTransform"] is None:
        return

    if side == "left":
        ring_value = self.ui.leftRingSlicer.value
        x = self.ui.leftLocalXSlicer.value
    else:
        ring_value = self.ui.rightRingSlicer.value
        x = self.ui.rightLocalXSlicer.value

    px, py, pz = plan["isocenter"]
    if side == "left":
        px -= 120
    else:
        px += 120

    arcTransform = vtk.vtkTransform()
    if side == "left":
        arcTransform.Translate(x, 0.0, 0.0)
    else:
        arcTransform.Translate(-x, 0.0, 0.0)

    arcTransform.Translate(px, py, pz)
    arcTransform.RotateX(360-ring_value)
    arcTransform.Translate(-px, -py, -pz)
    plan["ATStereo_Z_DriveTransform"].SetMatrixTransformToParent(arcTransform.GetMatrix())

  def axyzRotateSide(self, side):
    """This function applies the axyz rotate transform to the trajectory targets."""
    plan = self.trajectory_targets[side]

    if plan["ATStereo_Y_DriveTransform"] is None:
        return
    if plan["basePosition"] is None:
        return

    if side == "left":
        x = self.ui.leftLocalXSlicer.value
        y = self.ui.leftLocalYSlicer.value
        z = self.ui.leftLocalZSlicer.value
    else:
        x = self.ui.rightLocalXSlicer.value
        y = self.ui.rightLocalYSlicer.value
        z = self.ui.rightLocalZSlicer.value

    gx, gy, gz = self.localToGlobal(side, x, y, z)
    baseX, baseY, baseZ = plan["basePosition"]

    sliderTransform = vtk.vtkTransform()
    sliderTransform.Translate(0, gy - baseY, 0)
    plan["ATStereo_Y_DriveTransform"].SetMatrixTransformToParent(sliderTransform.GetMatrix())


  def slider_transform(self, side):
    """This function applies the slider transform to the trajectory targets."""
    plan = self.trajectory_targets[side]
    if plan["ATStereo_Y_DriveTransform"] is None or plan["ATStereo_X_DriveTransform"] is None:
        return

    if side == "left":
        x = self.ui.leftLocalXSlicer.value
        y = self.ui.leftLocalYSlicer.value
        z = self.ui.leftLocalZSlicer.value
        ring_value = self.ui.leftRingSlicer.value
    else:
        x = self.ui.rightLocalXSlicer.value
        y = self.ui.rightLocalYSlicer.value
        z = self.ui.rightLocalZSlicer.value
        ring_value = self.ui.rightRingSlicer.value

    supportTransform = vtk.vtkTransform()
    supportTransform.Translate(0.0, 0.0, -z)
    plan["ATStereo_X_DriveTransform"].SetMatrixTransformToParent(supportTransform.GetMatrix())

    arcTransform = vtk.vtkTransform()
    if side == "left":
        arcTransform.Translate(x, 0.0, 0.0)
    else:
        arcTransform.Translate(-x, 0.0, 0.0)
        
    px, py, pz = plan["isocenter"]
    if side == "left":
        px -= 120
    else:
        px += 120
        
    arcTransform.Translate(px, py, pz)
    arcTransform.RotateX(360-ring_value)
    arcTransform.Translate(-px, -py, -pz)
    
    plan["ATStereo_Z_DriveTransform"].SetMatrixTransformToParent(arcTransform.GetMatrix())
    # Update slider transform (Y local axis)
    slider_y = max(-60.0, min(120.0, y))
    sliderTransform = vtk.vtkTransform()
    sliderTransform.Translate(0.0, slider_y, 0.0)
    plan["ATStereo_Y_DriveTransform"].SetMatrixTransformToParent(sliderTransform.GetMatrix())
    
  def applyPlanTransform(self, side):
    """This function applies the plan transform to the trajectory targets."""
    plan = self.trajectory_targets[side]
    result = plan["result"]

    if result is None:
        return
    if plan["ATStereo_X_DriveTransform"] is None or plan["ATStereo_Y_DriveTransform"] is None:
        return
    if plan["ATStereo_Z_DriveTransform"] is None or plan["ATStereo_RingMountTransform"] is None or plan["ATStereo_TrajectoryGuideTransform"] is None:
        return

    x = result["x"]
    y = result["y"]
    z = result["z"]
    arc = result["arc"]
    ring = result["ring"]

    # Store the base position so manual sliders can offset relative to it
    gx, gy, gz = self.localToGlobal(side, x, y, z)
    plan["basePosition"] = (gx, gy, gz)

    # support moves along Z axis only
    supportTransform = vtk.vtkTransform()
    supportTransform.Translate(0.0, 0.0, z)
    plan["ATStereo_X_DriveTransform"].SetMatrixTransformToParent(supportTransform.GetMatrix())

    # slider moves along Y axis only
    sliderTransform = vtk.vtkTransform()
    sliderTransform.Translate(0.0, y, 0.0)
    plan["ATStereo_Y_DriveTransform"].SetMatrixTransformToParent(sliderTransform.GetMatrix())

    # arc: ring rotation with pivot at slider attachment AND sliding along X
    if side == "left":
        ring_value = ring
    else:
        ring_value = ring
    px, py, pz = plan["isocenter"]
    if side == "left":
        px -= 120

    else:
        px += 120

    arcTransform = vtk.vtkTransform()
    if side == "left":
        arcTransform.Translate(x, 0.0, 0.0)
    else:
        arcTransform.Translate(-x, 0.0, 0.0)

    arcTransform.Translate(px, py, pz)
    arcTransform.RotateX(360 - ring_value)
    arcTransform.Translate(-px, -py, -pz)
    plan["ATStereo_Z_DriveTransform"].SetMatrixTransformToParent(arcTransform.GetMatrix())

    # box: arc angle rotation around isocenter pivot
    arc_value = max(-10.0, min(60.0, arc))
    if side == "left":
        arc_value = -arc_value
        
    boxTransform = self._arcPivotTransform(side, arc_value)
    plan["ATStereo_RingMountTransform"].SetMatrixTransformToParent(boxTransform.GetMatrix())

    # path: identity — follows box as child in hierarchy
    pathTransform = vtk.vtkTransform()
    plan["ATStereo_TrajectoryGuideTransform"].SetMatrixTransformToParent(pathTransform.GetMatrix())

    # Apply manual slider adjustments on top or refresh UI state
    self.slider_transform(side)

    
  def visualFrame(self):
    if self.frameModel is not None:
      self.frameModel.GetDisplayNode().SetVisibility(1-self.frameModel.GetDisplayVisibility())

  def lockPlan(self):
    for side in ["left", "right"]:
        target = self.trajectory_targets[side]["target"]
        entry = self.trajectory_targets[side]["entry"]

        if target is not None:
            target.SetLocked(1 - target.GetLocked())
        if entry is not None:
            entry.SetLocked(1 - entry.GetLocked())


  # Data probe - capture mouse move on 3D view
  def setupDataProbecoordinates(self, x, y, z):
    """This function calculates the coordinates of the data probe in the local coordinate system of the left and right trajectories."""
    left_iso = self.trajectory_targets["left"]["isocenter"]
    right_iso = self.trajectory_targets["right"]["isocenter"]
    
    if x<0:
        x = x - left_iso[0]
        y = y - left_iso[1]
        z = z - left_iso[2]
        z = -z
        self.ui.leftProbeX.setText(f"{x:.2f}")
        self.ui.leftProbeY.setText(f"{y:.2f}")
        self.ui.leftProbeZ.setText(f"{z:.2f}")
        self.ui.rightProbeX.setText("0.00")
        self.ui.rightProbeY.setText("0.00")
        self.ui.rightProbeZ.setText("0.00")
    else:
        x = x - right_iso[0]
        y = y - right_iso[1]
        z = z - right_iso[2]
        z = -z
        x = -x
        self.ui.rightProbeX.setText(f"{x:.2f}")
        self.ui.rightProbeY.setText(f"{y:.2f}")
        self.ui.rightProbeZ.setText(f"{z:.2f}")
        self.ui.leftProbeX.setText("0.00")
        self.ui.leftProbeY.setText("0.00")
        self.ui.leftProbeZ.setText("0.00")        
        
            
  def onMouseMove(self, caller, event):
    try:
        pos = caller.GetEventPosition()

        layoutManager = slicer.app.layoutManager()
        threeDWidget = layoutManager.threeDWidget(0)
        threeDView = threeDWidget.threeDView()
        renderer = threeDView.renderWindow().GetRenderers().GetFirstRenderer()

        picker = vtk.vtkCellPicker()
        picker.SetTolerance(0.001)
        picker.Pick(pos[0], pos[1], 0, renderer)
        worldPos = picker.GetPickPosition()

        self.setupDataProbecoordinates(worldPos[0], worldPos[1], worldPos[2])
    except Exception as e:
        print("MouseMove Error:", e)

  def volumeRender(self):
    currentNode = self.ui.ctDataSelector.currentNode()
    if currentNode is None or not currentNode.IsA("vtkMRMLVolumeNode"):
        slicer.util.messageBox("Please load a volume first.")
        return

    volRenLogic = slicer.modules.volumerendering.logic()
    displayNode = volRenLogic.GetFirstVolumeRenderingDisplayNode(currentNode)
    if displayNode:
        isVisible = displayNode.GetVisibility()
        displayNode.SetVisibility(not isVisible)
        if not isVisible:
            self.ui.showBtn.setText("Hide 3D")
        else:
            self.ui.showBtn.setText("Show 3D")
    else:
        displayNode = volRenLogic.CreateDefaultVolumeRenderingNodes(currentNode)
        displayNode.SetVisibility(True)
        self.ui.showBtn.setText("Hide 3D")

    layoutManager = slicer.app.layoutManager()
    threeDWidget = layoutManager.threeDWidget(0)
    threeDView = threeDWidget.threeDView()
    threeDView.resetFocalPoint()
    slicer.util.resetSliceViews()

  def onVolumeChanged(self):
    currentNode = self.ui.ctDataSelector.currentNode()
    if currentNode is None or not currentNode.IsA("vtkMRMLVolumeNode"):
        self.ui.showBtn.setText("Show 3D")
        return

    volRenLogic = slicer.modules.volumerendering.logic()
    displayNode = volRenLogic.GetFirstVolumeRenderingDisplayNode(currentNode)
    if displayNode and displayNode.GetVisibility():
        self.ui.showBtn.setText("Hide 3D")
    else:
        self.ui.showBtn.setText("Show 3D")


class track:

    def __init__(self, parent=None):
       pass

    def startTrack(self, volumeNode, trackPointNode):
        """
        Main entry point for fiducial tracking. 
        Detects the physical boundary of the fiducial and applies a calibrated 1mm physical gap.
        """
        num_fiducials = trackPointNode.GetNumberOfControlPoints()
        rass = []

        for i in range(num_fiducials):
           ras = trackPointNode.GetNthControlPointPosition(i)
           ijk = self.RAS2IJK(volumeNode, ras)
           peak_ras = self.track3DPeak(volumeNode, ijk)
           rass.append(peak_ras)

        return rass

    def track3DPeak(self, volumeNode, start_ijk):
        """
        3D Columnar Peak Detection. Extracts a vertical 3D block above the starting point, thresholds it, 
        and calculates the centroid of the voxels at the maximum Z (k) index.
        """
        search_radius = 8
        threshold = 400
        
        start_i, start_j, start_k = start_ijk
        start_i = int(start_i)
        start_j = int(start_j)
        start_k = int(start_k)

        volume_array = slicer.util.array(volumeNode.GetID())
        k_max, j_max, i_max = volume_array.shape
        
        # Define 3D ROI bounds (extending upwards from start_k)
        i_min = max(0, start_i - search_radius)
        i_stop = min(i_max, start_i + search_radius + 1)
        j_min = max(0, start_j - search_radius)
        j_stop = min(j_max, start_j + search_radius + 1)
        k_min = max(0, start_k)
        k_stop = k_max
        
        if k_min >= k_stop:
            return self.IJK2RAS(volumeNode, start_ijk)
            
        roi = volume_array[k_min:k_stop, j_min:j_stop, i_min:i_stop]
        
        # Find voxels above threshold
        mask = roi >= threshold
        if not np.any(mask):
            return self.IJK2RAS(volumeNode, start_ijk)
            
        # Get coordinates of all valid voxels within the ROI
        z, y, x = np.where(mask)
        
        # The peak is the highest Z-coordinate (which corresponds to largest k offset)
        highest_z_offset = np.max(z)
        
        # Find the centroid of the voxels at this peak Z level for sub-voxel accuracy
        highest_z_mask = (z == highest_z_offset)
        peak_y_offsets = y[highest_z_mask]
        peak_x_offsets = x[highest_z_mask]
        
        # Voxel coordinates of the boundary
        peak_x = i_min + np.mean(peak_x_offsets)
        peak_y = j_min + np.mean(peak_y_offsets)
        peak_z = k_min + highest_z_offset
        
        # Convert boundary to RAS
        peak_ijk = [peak_x, peak_y, peak_z]
        boundary_ras = self.IJK2RAS(volumeNode, peak_ijk)
        
        # Determine physical direction of the k-axis (upward)
        peak_ijk_up = [peak_x, peak_y, peak_z + 1.0]
        boundary_ras_up = self.IJK2RAS(volumeNode, peak_ijk_up)
        
        import math
        dir_vector = [
            boundary_ras_up[0] - boundary_ras[0],
            boundary_ras_up[1] - boundary_ras[1],
            boundary_ras_up[2] - boundary_ras[2]
        ]
        magnitude = math.sqrt(dir_vector[0]**2 + dir_vector[1]**2 + dir_vector[2]**2)
        
        if magnitude > 0:
            norm_vector = [dir_vector[0]/magnitude, dir_vector[1]/magnitude, dir_vector[2]/magnitude]
            # Offset by precisely 1.0 mm
            boundary_ras[0] += norm_vector[0] * 1.0
            boundary_ras[1] += norm_vector[1] * 1.0
            boundary_ras[2] += norm_vector[2] * 1.0
            
        return boundary_ras

    def IJK2RAS(self, VolumeNode, ijk):
        ijk2ras = vtk.vtkMatrix4x4()
        VolumeNode.GetIJKToRASMatrix(ijk2ras)

        ijk_p = np.array([ijk[0], ijk[1], ijk[2], 1.0])
        ras_point = ijk2ras.MultiplyFloatPoint(ijk_p)
        return ras_point[:3]
    
    def RAS2IJK(self, VolumeNode, ras):
        rasToijk = vtk.vtkMatrix4x4()
        VolumeNode.GetRASToIJKMatrix(rasToijk)

        ras_p = np.array([ras[0], ras[1], ras[2], 1.0])
        ijk_point = np.round(rasToijk.MultiplyFloatPoint(ras_p))
        return ijk_point[:3]