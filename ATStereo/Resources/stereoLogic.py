import slicer
import math
import vtk
import numpy  as np


class stereoLogic:
    def __init__(self):
        self.plan=0

    def jumpToSlice(self,r,a,s):
        
        lm = slicer.app.layoutManager()
        for slice in ['Yellow','Green','Red']:
            sliceNode = lm.sliceWidget(slice).mrmlSliceNode()
            sliceNode.JumpSliceByOffsetting(r,a,s) 

    def calResult(self,target=None,entry=None):
      
        x = 100 - target[0]  #R
        y = 100 + target[1]  #A 
        z = 100 - target[2]  #S

        if entry is None:

            return ([round(x,2),round(y,2),round(z,2)])
      
        else:

            nr = entry[0] - target[0]
            na = entry[1] - target[1]
            ns = entry[2] - target[2]
        #################################################  Com Line Target-Entry and R Axial degree，not projection
      
            n_magnitude = math.sqrt(nr**2 + na**2 + ns**2) 

            if n_magnitude == 0: #the same point
                arc=0
            else:
                arc =abs(math.degrees(math.acos(nr / n_magnitude)))
      
        ################################################### for ring-bias
            ring_bias =math.atan2(na ,ns) * 180 / math.pi

            if na >= 0 and ns >= 0:  #0∼90
             ring = 90 - ring_bias

            elif na < 0  and ns >= 0: #-90∼0
                ring = 90 -ring_bias

            elif na > 0 and ns <  0: # 90 ∼180
                ring = 90 - ring_bias

            elif na < 0 and ns <  0: #−180 ∼ −90
                ring = 90 - ring_bias  
      
            return([round(x,2),round(y,2),round(z,2),round(arc,2),round(ring,2)])
        
    def initTube(self):
        self.vtkTube = vtk.vtkCylinderSource() 
        self.vtkTube.SetRadius(2)
        self.vtkTube.SetResolution(20)

        self.transform = vtk.vtkTransform()
        self.transform_filter = vtk.vtkTransformPolyDataFilter()
        self.transform_filter.SetTransform(self.transform)
        self.transform_filter.SetInputConnection(self.vtkTube.GetOutputPort())

    def updateTube(self,p1,p2):
        
        height = np.linalg.norm(np.array(p2) - np.array(p1))
        center = [(p1[i] + p2[i]) / 2 for i in range(3)]

        direction = np.array(p2) - np.array(p1)
        direction = direction / np.linalg.norm(direction)

        self.vtkTube.SetHeight(height)

        default_direction = np.array([0, 1, 0])  # VTK default direction is Y axis
        rotation_axis = np.cross(default_direction, direction)
        angle = np.arccos(np.dot(default_direction, direction)) * 180.0 / np.pi

        self.transform.Identity()  # Reset transform
        self.transform.Translate(*center)  # Translate first
        if np.linalg.norm(rotation_axis) > 1e-6:
            self.transform.RotateWXYZ(angle, *rotation_axis)

        self.transform_filter.Update()

        return self.transform_filter 
    
    def addPlan(self,tubeModelNode=None):  #copy a tube
        self.plan += 1
        name="plan"+str(self.plan)
        if tubeModelNode:
            shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
            IDToClone = shNode.GetItemByDataNode(tubeModelNode)
            ID = slicer.modules.subjecthierarchy.logic().CloneSubjectHierarchyItem(shNode, IDToClone)
            clonedNode = shNode.GetItemDataNode(ID)
            clonedNode.GetDisplayNode().SetColor(1,1,0)
            clonedNode.SetName(name)


    def kabsch(self,P,Q):
        # Kabsch algorithm
        # Step 1: Compute centroid
        P_centroid = np.mean(P, axis=0)  # Source point set centroid
        Q_centroid = np.mean(Q, axis=0)  # Target point set centroid

        # Step 2: Center
        P_centered = P - P_centroid  # (4, 3)
        Q_centered = Q - Q_centroid  # (4, 3)

        # Step 3: Compute covariance matrix H
        H = P_centered.T @ Q_centered  # (3, 3)

        # Step 4: Singular Value Decomposition (SVD)
        U, _, Vt = np.linalg.svd(H)  # U (3, 3), Vt (3, 3)

        # Step 5: Compute rotation matrix R
        d = np.sign(np.linalg.det(Vt.T @ U.T))  # Ensure determinant of rotation matrix is positive
        D = np.eye(3)  # Identity matrix
        D[2, 2] = d    # Adjust determinant
        R = Vt.T @ D @ U.T  # Rotation matrix (3, 3)

        # Step 6: Compute translation vector t
        t = Q_centroid - R @ P_centroid  # (3,)

        # Build 4x4 transformation matrix
        calculatedTransform = vtk.vtkMatrix4x4()
        for i in range(3):
            for j in range(3):
                calculatedTransform.SetElement(i, j, R[i, j])  # Set rotation part
            calculatedTransform.SetElement(i, 3, t[i])        # Set translation part
        calculatedTransform.SetElement(3, 3, 1)   

        return calculatedTransform