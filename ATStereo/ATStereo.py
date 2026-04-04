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
    self.parent.title = "ATStereo"  # TODO: make this more human readable by adding spaces
    self.parent.categories = ["Neurosurgery"] 
    self.parent.dependencies = []  # TODO: add here list of module names that this module requires
    self.parent.contributors = ["xmszj"]  # TODO: replace with "Firstname Lastname (Organization)"
    # TODO: update with short description of the module and a link to online module documentation
    self.parent.helpText = """https://github.com/xmszj/BrainStereo"""
    # TODO: replace with organization, grant and thanks
    self.parent.acknowledgementText = """Thanks for 3DSlicer Forum """

class ATStereoWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):

  def __init__(self, parent=None):
    ScriptedLoadableModuleWidget.__init__(self, parent)
    VTKObservationMixin.__init__(self)  
    self.logic = None

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)

    uiWidget = slicer.util.loadUI(self.resourcePath('UI/BrainStereo.ui'))
    self.layout.addWidget(uiWidget)
    self.ui = slicer.util.childWidgetVariables(uiWidget)
    uiWidget.setMRMLScene(slicer.mrmlScene)

    self.ui.btn_choose_point.connect('clicked(bool)', self.on_choose_four_point)

    self.ui.btn_choose_left_target_point.connect('clicked(bool)', self.on_add_target_point_left)
    self.ui.btn_choose_left_entry_point.connect('clicked(bool)', self.on_add_entry_point_left)
    self.ui.btn_choose_right_target_point.connect('clicked(bool)', self.on_add_target_point_right)
    self.ui.btn_choose_right_entry_point.connect('clicked(bool)', self.on_add_entry_point_right)

    self.ui.ctDataSelector.setMRMLScene(slicer.mrmlScene)
    self.ui.btn_clear.connect('clicked(bool)', self.reset)
    
    #transform - per-side arc angle and ring sliders
    self.ui.leftArcSlicer.valueChanged.connect(lambda: self.pRotateSide("left"))
    self.ui.leftRingSlicer.valueChanged.connect(lambda: self.ringRotateSide("left"))
    self.ui.rightArcSlicer.valueChanged.connect(lambda: self.pRotateSide("right"))
    self.ui.rightRingSlicer.valueChanged.connect(lambda: self.ringRotateSide("right"))
    self.ui.axTransSlicer.valueChanged.connect(self.axyzRotateBoth)
    self.ui.ayTransSlicer.valueChanged.connect(self.axyzRotateBoth)
    self.ui.azTransSlicer.valueChanged.connect(self.axyzRotateBoth)

    self.ui.visualizePlanBtn.connect('clicked(bool)', self.loadFrame)
    self.ui.visualizeFrameBtn.connect('clicked(bool)', self.visualFrame)
    self.ui.lockPlanBtn.connect('clicked(bool)', self.lockPlan)
    #self.ui.realTImeBtn.connect('clicked(bool)', self.realTimeTrac)

    self.ui.showBtn.connect('clicked(bool)', self.volumeRender)

    
    self.ui.newPlanBtn.connect('clicked(bool)', self.newPlan)

    self.ui.btn_autoReg.connect('clicked(bool)', self.autoFourpoints)

    self.ui.testBtn.connect('clicked(bool)', self.loadTestCt)

    

    self.defineiVar()

    # self.leksellLib = ctypes.CDLL(slicer.util.loadUI(self.resourcePath('pythonDll.dll')))
    # lib.calculate_xyz lib.calculate_arc  lib.calculate_ring


    #shNode = slicer.mrmlScene.GetSubjectHierarchyNode()
    #sceneItemID = shNode.GetSceneItemID()
    #folderItemId = shNode.CreateFolderItem(sceneItemID , "BrainStereo")

    self.sc=stereoLogic()
    self.sc.initTube()

    self.track=track()

    #self.creatPlanTable()


  def localToGlobal(self, side, x, y, z):
    if side == "left":
        gx = x
    else:
        gx = 200 - x
    gy = y
    gz = z
    return gx, gy, gz


  def defineiVar(self):
    self.sPoints = None
    self.fourPoints = None
    self.outputTransformNode = None
    self.frameModel = None
    self.realTimeVis = False

    self.plans = {
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

            "supportTranNode": None,
            "sliderTranNode": None,
            "arcTranNode": None,
            "boxTranNode": None,
            "pathTranNode": None,

            "result": None,
            "offset": None,
            "basePosition": None,
            "isocenter": (-100.0, -100.0, 100.0),
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

            "supportTranNode": None,
            "sliderTranNode": None,
            "arcTranNode": None,
            "boxTranNode": None,
            "pathTranNode": None,

            "result": None,
            "offset": None,
            "basePosition": None,
            "isocenter": (100.0, -100.0, 100.0),
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
  def creatPlanTable(self):
        table=self.ui.planTable
        table.horizontalHeader().setSectionResizeMode(0, 1)
        table.horizontalHeader().setSectionResizeMode(1, 1)
        table.horizontalHeader().setSectionResizeMode(2, 1)
        table.horizontalHeader().setSectionResizeMode(3, 1)
        table.horizontalHeader().setSectionResizeMode(4, 2)
        table.horizontalHeader().setSectionResizeMode(5, 2)

  def showStandPoints(self,points): # show standard points

    self.sPoints = slicer.mrmlScene.GetFirstNodeByName("S")
    if (self.sPoints is None):
      self.sPoints = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "S")
    self.sPoints.RemoveAllControlPoints()

    self.sPoints.SetLocked(1)
     
    display_node = self.sPoints.GetDisplayNode()
    display_node.SetGlyphType(5)
    display_node.SetTextScale(3)
    
    for i in points:
      self.sPoints.AddFiducial(i[0],i[1],i[2])

    #rename 4 points
    name=["A  ","B  ","C  ","D  "]

    for i in range(4):
      self.sPoints.SetNthControlPointLabel(i, name[i])

  def on_choose_four_point(self):#select 4 points
    self.max2D()
    self.fourPoints= slicer.mrmlScene.GetFirstNodeByName("pointset")
    if(self.fourPoints is None):
        #slicer.app.layoutManager().threeDWidget(0).threeDView().lookFromAxis(3)
        self.fourPoints= slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "pointset")
        self.fourPoints.RemoveAllControlPoints()

    self.fourPoints.GetDisplayNode().SetGlyphType(2)
    
    self.fourPoints.RemoveAllObservers()
    self.fourPoints.AddObserver(
    slicer.vtkMRMLMarkupsNode.PointAddedEvent,
    functools.partial(self.on_four_point_added, actor="f"))

    interactionNode = slicer.app.applicationLogic().GetInteractionNode()
    selectionNode = slicer.app.applicationLogic().GetSelectionNode()
    selectionNode.SetActivePlaceNodeID(self.fourPoints.GetID())
    placeModePersistence = 1
    interactionNode.SetPlaceModePersistence(placeModePersistence)
    interactionNode.SetCurrentInteractionMode(interactionNode.Place)
   
    pointListDisplayNode = self.fourPoints.GetDisplayNode()
    pointListDisplayNode.SetSelectedColor(1,1,0)


  def max2D(self):
    layoutManager = slicer.app.layoutManager()
    layoutManager.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUpRedSliceView)
    redSliceCompositeNode = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceCompositeNodeRed")
    if redSliceCompositeNode:
        redSliceCompositeNode.SetBackgroundVolumeID(redSliceCompositeNode.GetBackgroundVolumeID())
  
  def fourUp(self):

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
  
  def changeOrder(self,vtkpoints):#creat order for 4 points

    from_new = []
    for i in range(4):
        point = [0, 0, 0] 
        vtkpoints.GetPoint(i, point) 
        from_new.append(point) 

    # order by x
    points_sorted_by_x = sorted(from_new, key=lambda point: point[0], reverse=True)

    x_max_points = points_sorted_by_x[:2]

    x_max_points_sorted_by_y = sorted(x_max_points, key=lambda point: point[1], reverse=True)
    B = x_max_points_sorted_by_y[0]
    C = x_max_points_sorted_by_y[1]

    remaining_points = points_sorted_by_x[2:]
    remaining_points_sorted_by_y = sorted(remaining_points, key=lambda point: point[1], reverse=True)
    A = remaining_points_sorted_by_y[0]
    D= remaining_points_sorted_by_y[1]

    from_new.clear()
    from_new.append(A)
    from_new.append(B)
    from_new.append(C)
    from_new.append(D)

    from_points_vtk = vtk.vtkPoints() 
    for point in from_new:
      from_points_vtk.InsertNextPoint(point)

    return from_points_vtk,from_new
  
  def autoFourpoints(self):
      if self.fourPoints is None :
        slicer.util.messageBox("Please Select 4 Points")
        return
      n = self.fourPoints.GetNumberOfControlPoints()
      if n != 4:
        slicer.util.messageBox("Please Select 4 Points")
        return
      
      leksell = self.ui.ctDataSelector.currentNode()
      rass=self.track.startTrack(leksell,self.fourPoints)
      for i in range(4):
         self.fourPoints.SetNthControlPointPosition(i,rass[i])

      self.on_register_point()
         
  def on_register_point(self):#to register
    self.fourUp()

    stan=self.comStandLocation() 

    self.showStandPoints(stan) 

    if self.fourPoints is None :
      slicer.util.messageBox("Please Select 4 Points")
      return
    n = self.fourPoints.GetNumberOfControlPoints()
    if n != 4:
      slicer.util.messageBox("Please Select 4 Points")
      return

    fromPointsOrdered = vtk.vtkPoints()
    toPointsOrdered = vtk.vtkPoints()

    for i in range(4):
      ras = vtk.vtkVector3d(0,0,0)
      self.fourPoints.GetNthControlPointPositionWorld(i,ras)
      fromPointsOrdered.InsertPoint(i, ras)
      toPointsOrdered.InsertPoint(i, stan[i])

    P = np.array([fromPointsOrdered.GetPoint(i) for i in range(4)]) 
    Q = np.array([toPointsOrdered.GetPoint(i) for i in range(4)])  
    #calculatedTransform =self.sc.kabsch(P,Q)

    landmarkTransform = vtk.vtkLandmarkTransform()
    landmarkTransform.SetSourceLandmarks(fromPointsOrdered)
    landmarkTransform.SetTargetLandmarks(toPointsOrdered)
    landmarkTransform.SetModeToSimilarity()
    landmarkTransform.Update()
    calculatedTransform = vtk.vtkMatrix4x4()
    landmarkTransform.GetMatrix(calculatedTransform)

    self.outputTransformNode = slicer.mrmlScene.GetFirstNodeByName("pTrans")
    if(self.outputTransformNode is None):
      self.outputTransformNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTransformNode", "pTrans")
    self.outputTransformNode.SetMatrixTransformToParent(calculatedTransform)
    self.fourPoints.SetAndObserveTransformNodeID(self.outputTransformNode.GetID())

    leksell = self.ui.ctDataSelector.currentNode()
    if leksell:
      leksell.SetAndObserveTransformNodeID(self.outputTransformNode.GetID())

    layoutManager = slicer.app.layoutManager()
    threeDWidget = layoutManager.threeDWidget(0) 
    threeDView = threeDWidget.threeDView()
    threeDView.resetFocalPoint() 
    slicer.util.resetSliceViews()
    
   
    total_error = 0.0
    num_points = fromPointsOrdered.GetNumberOfPoints()

    for i in range(num_points):

        source_point = [0.0, 0.0, 0.0]
        fromPointsOrdered.GetPoint(i, source_point)
      
        transformed_point = [0.0, 0.0, 0.0]
        landmarkTransform.TransformPoint(source_point, transformed_point)
        
        target_point = [0.0, 0.0, 0.0]
        toPointsOrdered.GetPoint(i, target_point)
        
        error = math.sqrt(
            (transformed_point[0] - target_point[0])**2 + 
            (transformed_point[1] - target_point[1])**2 + 
            (transformed_point[2] - target_point[2])**2 
        )
        
        total_error += error

    rms_error =round(total_error / num_points,2)
    if rms_error>1.5:
       slicer.util.warningDisplay("The error is too large. Please re-register.", windowTitle="Warning")

    self.ui.errortext.setText(str(rms_error))
  
  def hidePoints(self):
    node1= self.fourPoints
    node2= self.sPoints
    if node1 and node2:
      node1.GetDisplayNode().SetVisibility(0)
      node2.GetDisplayNode().SetVisibility(0)

####################################################################################### for target and entry

  def on_add_target_point_left(self):
      self.hidePoints()
      self.plans["left"]["target"] = self.createPlanPointNode("targetPointLeft", "t_left")

  def on_add_entry_point_left(self):
      self.plans["left"]["entry"] = self.createPlanPointNode("entryPointLeft", "e_left")

  def on_add_target_point_right(self):
      self.hidePoints()
      self.plans["right"]["target"] = self.createPlanPointNode("targetPointRight", "t_right")

  def on_add_entry_point_right(self):
      self.plans["right"]["entry"] = self.createPlanPointNode("entryPointRight", "e_right")

  
  def newPlan(self):
    for side in ["left", "right"]:
        tube = self.plans[side]["tubeModel"]
        if tube is not None:
            self.sc.addPlan(tube)


####################################################################################### Observer 
  def on_plan_point_modified(self, caller, event, actor=None):
    if actor in ["t_left", "e_left"]:
        self.updatePlan("left")
    elif actor in ["t_right", "e_right"]:
        self.updatePlan("right")

    if self.realTimeVis:
        self.loadFrame()

  def updatePlan(self, side):
    self.updatePlanResult(side)
    self.updatePlanTube(side)
    self.applyPlanTransform(side)
    self.checkTrajectorySeparation()

  def updatePlanResult(self, side):
    plan = self.plans[side]
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

    if side == "left":
        self.ui.left_final_x.setText(str(result["x"]))
        self.ui.left_final_y.setText(str(result["y"]))
        self.ui.left_final_z.setText(str(result["z"]))
        self.ui.leftSlider.setText(str(result["slider"]))
        self.ui.leftArc.setText(str(result["arc"]))
        self.ui.leftRing.setText(str(result["ring"]))
    else:
        self.ui.right_final_x.setText(str(result["x"]))
        self.ui.right_final_y.setText(str(result["y"]))
        self.ui.right_final_z.setText(str(result["z"]))
        self.ui.rightSlider.setText(str(result["slider"]))
        self.ui.rightArc.setText(str(result["arc"]))
        self.ui.rightRing.setText(str(result["ring"]))

  def computeDualArcResult(self, side, target_ras, entry_ras=None):
    t = np.array([target_ras[0], target_ras[1], target_ras[2]], dtype=float)

    print(f"[{side}] raw target_ras = {t}")

    frame_x = t[0]
    frame_y = t[1]
    frame_z = t[2]

    if side == "left":
        local_x = frame_x
    else:
        local_x = 200.0 - frame_x

    local_y = frame_y
    local_z = frame_z

    print(f"[{side}] preclamp local = ({local_x}, {local_y}, {local_z})")

    local_x = max(0.0, min(200.0, local_x))
    local_y = max(0.0, min(200.0, local_y))
    local_z = max(-200.0, min(200.0, local_z))

    slider = max(0.0, min(100.0, local_y))

    if entry_ras is not None:
        e = np.array([entry_ras[0], entry_ras[1], entry_ras[2]], dtype=float)
        # Direction vector from entry to target (Globocentric convention)
        a = [t[i] - e[i] for i in range(3)]
        A = math.sqrt(sum(v * v for v in a))

        if A < 1e-6:
            return None

        # Arc angle: from X axis (Globocentric)
        val_arc = max(-1.0, min(1.0, a[0] / A))
        arc = 90.0 - math.degrees(math.acos(val_arc))
        arc = max(0.0, min(180.0, abs(arc)))

        # Ring angle: computed from Y/Z plane with quadrant logic (Globocentric)
        if abs(a[1]) < 1e-12:
            alpha_y = 90.0
        else:
            alpha_y = math.degrees(math.atan(abs(a[2]) / abs(a[1])))

        diffZ = abs(t[2]) - abs(e[2])

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
                ring = 180.0 + alpha_y
        else:
            ring = 0.0
    else:
        arc = 30.0
        ring = 0.0

    print(f"[{side}] final local = ({local_x}, {local_y}, {local_z}), slider={slider}, arc={arc}, ring={ring}")

    return {
        "x": round(local_x, 2),
        "y": round(local_y, 2),
        "z": round(local_z, 2),
        "slider": round(slider, 2),
        "arc": round(arc, 2),
        "ring": round(ring, 2),
    }


  def checkTrajectorySeparation(self, minDistanceMm=5.0):
    left = self.plans["left"]
    right = self.plans["right"]

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
      self.fourPoints = slicer.mrmlScene.GetFirstNodeByName("pointset")
      node=self.fourPoints
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
          _,nodeListPoints=self.changeOrder(nodeVtkPoints)
          node.RemoveAllControlPoints()
          node.GetDisplayNode().SetGlyphType(2)
          name=["    a","    b","    c","    d"]
          for i in range(4):
            node.AddControlPointWorld(nodeListPoints[i])
            node.SetNthControlPointLabel(i,name[i])

  def on_four_point_added(self, caller, event, actor=None):
    self.observeFourPoints()

  def updatePlanTube(self, side):
    plan = self.plans[side]

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
        tube = self.plans[side]["tubeModel"]
        if tube is not None:
            tube.GetDisplayNode().SetVisibility(0)
 
  def observerEndMove(self, caller, event):
    for side in ["left", "right"]:
        tube = self.plans[side]["tubeModel"]
        if tube is not None:
            tube.GetDisplayNode().SetVisibility(1)
    self.syncPlan()
  
  
  def reset(self):
    nodeList = [
        self.sPoints,
        self.fourPoints,
        self.outputTransformNode,
        self.frameModel,
    ]

    for side in ["left", "right"]:
      plan = self.plans[side]
      nodeList.extend([
          plan["target"],
          plan["entry"],
          plan["tubeModel"],
          plan["supportModel"],
          plan["sliderModel"],
          plan["arcModel"],
          plan["boxModel"],
          plan["pathModel"],
          plan["axialModel"],
          plan["supportTranNode"],
          plan["sliderTranNode"],
          plan["arcTranNode"],
          plan["boxTranNode"],
          plan["pathTranNode"],
      ])

    for node in nodeList:
        if node is not None:
            slicer.mrmlScene.RemoveNode(node)

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

    self.ui.leftSlider.setText("0")
    self.ui.rightSlider.setText("0")
    self.ui.depthEdit.setText("120")
    self.defineiVar()

#######################################################################################  For Simulation
  def loadFrame(self):
    if self.frameModel is None:
        self.frameModel = slicer.util.loadModel(self.resourcePath('frame/Frame.stl'))
        self.frameModel.GetDisplayNode().SetColor(1, 238/255, 0)

    self.loadPlanModels("left", "Supportleft.stl", "Sliderleft.stl", "QuarterArc.stl", "Box.stl", "Pathleft.stl", "Axialleft.stl")
    self.loadPlanModels("right", "Supportright.stl", "Sliderright.stl", "QuarterArcright.stl", "Boxright.stl", "Pathright.stl", "Axial.stl")

    self.syncPlan()

    self.applyPlanTransform("left")
    self.applyPlanTransform("right")

  def loadPlanModels(self, side, supportFile, sliderFile, arcFile, boxFile, pathFile, axialFile):
      plan = self.plans[side]

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

      if plan["supportTranNode"] is None:
          plan["supportTranNode"] = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTransformNode", f"supportTran_{side}")

      if plan["sliderTranNode"] is None:
          plan["sliderTranNode"] = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTransformNode", f"sliderTran_{side}")

      if plan["arcTranNode"] is None:
          plan["arcTranNode"] = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTransformNode", f"arcTran_{side}")

      if plan["boxTranNode"] is None:
          plan["boxTranNode"] = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTransformNode", f"boxTran_{side}")

      if plan["pathTranNode"] is None:
          plan["pathTranNode"] = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTransformNode", f"pathTran_{side}")

      plan["supportModel"].SetAndObserveTransformNodeID(plan["supportTranNode"].GetID())
      plan["sliderModel"].SetAndObserveTransformNodeID(plan["sliderTranNode"].GetID())
      plan["arcModel"].SetAndObserveTransformNodeID(plan["arcTranNode"].GetID())
      plan["boxModel"].SetAndObserveTransformNodeID(plan["boxTranNode"].GetID())
      plan["pathModel"].SetAndObserveTransformNodeID(plan["pathTranNode"].GetID())
      plan["axialModel"].SetAndObserveTransformNodeID(plan["boxTranNode"].GetID())

      # hierarchy
      plan["sliderTranNode"].SetAndObserveTransformNodeID(plan["supportTranNode"].GetID())
      plan["arcTranNode"].SetAndObserveTransformNodeID(plan["sliderTranNode"].GetID())
      plan["boxTranNode"].SetAndObserveTransformNodeID(plan["arcTranNode"].GetID())
      plan["pathTranNode"].SetAndObserveTransformNodeID(plan["boxTranNode"].GetID())

  def loadTestCt(self):
     ctPath=self.resourcePath('ctData/test_CT.nrrd')
     slicer.util.loadVolume(ctPath)
     self.ui.ctDataSelector.setCurrentNode(slicer.util.getNode("test_CT"))

  def syncPlan(self):
    for side in ["left", "right"]:
        self.applyPlanTransform(side)

  def _arcPivotTransform(self, side, arc_value):
    """Create a transform that rotates around the side's isocenter by arc_value degrees (Y axis)."""
    px, py, pz = self.plans[side]["isocenter"]
    t = vtk.vtkTransform()
    t.Translate(px, py, pz)
    t.RotateY(arc_value)
    t.Translate(-px, -py, -pz)
    return t

  def _ringPivotTransform(self, side, ring_value):
    """Create a transform that rotates around the side's isocenter by ring_value degrees (X axis)."""
    px, py, pz = self.plans[side]["isocenter"]
    t = vtk.vtkTransform()
    t.Translate(px, py, pz)
    t.RotateX(ring_value)
    t.Translate(-px, -py, -pz)
    return t

  def pRotateSide(self, side):
    plan = self.plans[side]
    if plan["boxTranNode"] is None:
        return

    if side == "left":
        arc_value = -self.ui.leftArcSlicer.value
    else:
        arc_value = self.ui.rightArcSlicer.value

    boxTransform = self._arcPivotTransform(side, arc_value)
    plan["boxTranNode"].SetMatrixTransformToParent(boxTransform.GetMatrix())

  def ringRotateSide(self, side):
    plan = self.plans[side]
    if plan["arcTranNode"] is None:
        return

    if side == "left":
        ring_value = self.ui.leftRingSlicer.value
    else:
        ring_value = -self.ui.rightRingSlicer.value

    px, py, pz = plan["isocenter"]
    if side == "left":
        px -= 190
    else:
        px += 190

    arcTransform = vtk.vtkTransform()
    arcTransform.Translate(px, py, pz)
    arcTransform.RotateX(ring_value)
    arcTransform.Translate(-px, -py, -pz)
    plan["arcTranNode"].SetMatrixTransformToParent(arcTransform.GetMatrix())

  def axyzRotateBoth(self):
    self.axyzRotateSide("left")
    self.axyzRotateSide("right")

  def axyzRotateSide(self, side):
    plan = self.plans[side]

    if plan["sliderTranNode"] is None:
        return
    if plan["basePosition"] is None:
        return

    x = self.ui.axTransSlicer.value
    y = self.ui.ayTransSlicer.value
    z = self.ui.azTransSlicer.value

    gx, gy, gz = self.localToGlobal(side, x, y, z)
    baseX, baseY, baseZ = plan["basePosition"]

    sliderTransform = vtk.vtkTransform()
    sliderTransform.Translate(0, gy - baseY, 0)
    plan["sliderTranNode"].SetMatrixTransformToParent(sliderTransform.GetMatrix())

  def applyPlanTransform(self, side):
    plan = self.plans[side]
    result = plan["result"]

    if result is None:
        return
    if plan["supportTranNode"] is None or plan["sliderTranNode"] is None:
        return
    if plan["arcTranNode"] is None or plan["boxTranNode"] is None or plan["pathTranNode"] is None:
        return

    x = result["x"]
    y = result["y"]
    z = result["z"]
    slider = result["slider"]
    arc = result["arc"]
    ring = result["ring"]

    # Store the base position so manual sliders can offset relative to it
    gx, gy, gz = self.localToGlobal(side, x, y, z)
    plan["basePosition"] = (gx, gy, gz)

    # support moves along Z axis only
    supportTransform = vtk.vtkTransform()
    supportTransform.Translate(0.0, 0.0, z)
    plan["supportTranNode"].SetMatrixTransformToParent(supportTransform.GetMatrix())

    # slider moves along Y axis only
    sliderTransform = vtk.vtkTransform()
    sliderTransform.Translate(0.0, slider, 0.0)
    plan["sliderTranNode"].SetMatrixTransformToParent(sliderTransform.GetMatrix())

    # arc: ring rotation with pivot at slider attachment
    if side == "left":
        ring_value = ring
    else:
        ring_value = -ring
    px, py, pz = plan["isocenter"]
    if side == "left":
        px -= 190

    else:
        px += 190

    arcTransform = vtk.vtkTransform()
    arcTransform.Translate(px, py, pz)
    arcTransform.RotateX(ring_value)
    arcTransform.Translate(-px, -py, -pz)
    plan["arcTranNode"].SetMatrixTransformToParent(arcTransform.GetMatrix())

    # box: arc angle rotation around isocenter pivot
    arc_value = max(0.0, min(180.0, arc))
    if side == "left":
        arc_value = -arc_value

    boxTransform = self._arcPivotTransform(side, arc_value)
    plan["boxTranNode"].SetMatrixTransformToParent(boxTransform.GetMatrix())

    # path: identity — follows box as child in hierarchy
    pathTransform = vtk.vtkTransform()
    plan["pathTranNode"].SetMatrixTransformToParent(pathTransform.GetMatrix())

    
  def visualFrame(self):
    if self.frameModel is not None:
      self.frameModel.GetDisplayNode().SetVisibility(1-self.frameModel.GetDisplayVisibility())

  def realTimeTrac(self):
    self.realTimeVis = not self.realTimeVis

  def lockPlan(self):
    for side in ["left", "right"]:
        target = self.plans[side]["target"]
        entry = self.plans[side]["entry"]

        if target is not None:
            target.SetLocked(1 - target.GetLocked())
        if entry is not None:
            entry.SetLocked(1 - entry.GetLocked())



  def volumeRender(self):
    currentNode = self.ui.ctDataSelector.currentNode()
    if currentNode is None:
        slicer.util.messageBox("Please load a volume first.")
        return

    volRenLogic = slicer.modules.volumerendering.logic()
    displayNode = volRenLogic.CreateDefaultVolumeRenderingNodes(currentNode)
    displayNode.SetVisibility(True)

    layoutManager = slicer.app.layoutManager()
    threeDWidget = layoutManager.threeDWidget(0)
    threeDView = threeDWidget.threeDView()
    threeDView.resetFocalPoint()
    slicer.util.resetSliceViews()


class track:

    def __init__(self, parent=None):
       pass


    def startTrack(self,volumeNode,trackPointNode):

        trackPoint= trackPointNode

        num_fiducials = trackPoint.GetNumberOfControlPoints()

        rass=[]

        for i in range(num_fiducials):
           ras = trackPoint.GetNthControlPointPosition(i)

           ijk=self.RAS2IJK(volumeNode,ras)

           ras=self.trackLogic(volumeNode,ijk[0],ijk[1])
           rass.append(ras)

        return rass


    def trackLogic(self,volumeNode=None,i=None,j=None):

        search_radius=8

        k,off=self.getIndex()

        ori_array  = slicer.util.array(volumeNode.GetID())

        ks=ori_array.shape[0]-k
 
        center_x = i 
        center_y = j 

        for i in range(ks):
            index = k + i
            img = ori_array[index, :, :]

            y_min = int(max(0, center_y - search_radius))
            y_max = int(min(img.shape[0], center_y + search_radius))
            x_min = int(max(0, center_x - search_radius))
            x_max = int(min(img.shape[1], center_x + search_radius))

            roi = img[y_min:y_max, x_min:x_max]
            maxVal = np.max(roi)
            maxLoc = np.unravel_index(np.argmax(roi), roi.shape) 

            if maxVal <400:
              break

            center_x = x_min + maxLoc[1]
            center_y = y_min + maxLoc[0]

            cor=[center_x, center_y,index]
            ras=self.IJK2RAS(volumeNode,cor)

        if ras is None:
          raise ValueError("trackLogic failed: ras was never computed")
            
        return ras

    
    def IJK2RAS(self,VolumeNode,ijk):
        
        ijk2ras = vtk.vtkMatrix4x4()
        VolumeNode.GetIJKToRASMatrix(ijk2ras)

        ijk_p=np.array([ijk[0], ijk[1], ijk[2]] + [1.0])
        
        ras_point =ijk2ras.MultiplyFloatPoint(ijk_p)
        return ras_point[:3]
    
    def RAS2IJK(self,VolumeNode,ras):
        rasToijk = vtk.vtkMatrix4x4()
        VolumeNode.GetRASToIJKMatrix(rasToijk)

        ras_p = np.array([ras[0], ras[1], ras[2], 1.0])
        ijk_point =np.round(rasToijk.MultiplyFloatPoint(ras_p))
        
        return ijk_point[:3]

    def getIndex(self):

        red_logic = slicer.app.layoutManager().sliceWidget("Red").sliceLogic()
        offset=red_logic.GetSliceOffset()
        k=red_logic.GetSliceIndexFromOffset(offset)-1
        return k,offset


    def jumpTok(self,offset=0):
        red_logic = slicer.app.layoutManager().sliceWidget("Red").sliceLogic()
        red_logic.SetSliceOffset(offset)

    def otherInfo(volumeNode):
        ScalarRange= volumeNode.GetImageData().GetScalarRange()
        Bounds=volumeNode.GetImageData().GetBounds()
        Center=volumeNode.GetImageData().GetCenter()
        Dimensions=volumeNode.GetImageData().GetDimensions()
        DirectionMatrix=volumeNode.GetImageData().GetDirectionMatrix()