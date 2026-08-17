import vtk
import numpy as np
import slicer

class HeadFrameRegistration:
    def __init__(self):
        self.masterVolumeNode = None
        self.segmentationNode = None
        self.segmentEditorWidget = None
        self.segmentEditorNode = None
        self.segmentId = None
        self.BeforeSegmentationNode = None
        
    def initSegment(self, masterVolumeNode=None):
        if (self.masterVolumeNode == None):
            if masterVolumeNode:
                self.masterVolumeNode = masterVolumeNode
            else:
                self.masterVolumeNode = slicer.mrmlScene.GetFirstNodeByClass('vtkMRMLScalarVolumeNode')
            slicer.modules.segmenteditor.widgetRepresentation()
            slicer.modules.segmenteditor.widgetRepresentation().self().enter()
            self.BeforeSegmentationNode = slicer.mrmlScene.GetFirstNodeByClass('vtkMRMLSegmentationNode')
            if self.BeforeSegmentationNode:
                self.segmentationNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLSegmentationNode')
                self.segmentationNode.CreateDefaultDisplayNodes()
            else:
                self.segmentationNode = self.BeforeSegmentationNode
            self.segmentEditorWidget = slicer.modules.segmenteditor.widgetRepresentation().self().editor
            if len(slicer.util.getNodesByClass("vtkMRMLSegmentEditorNode")) > 0:
                self.segmentEditorNode = slicer.util.getNodesByClass("vtkMRMLSegmentEditorNode")[0]
            else:
                self.segmentEditorNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLSegmentEditorNode')
            self.segmentEditorWidget.setMRMLSegmentEditorNode(self.segmentEditorNode)
            self.segmentEditorWidget.setSegmentationNode(self.segmentationNode)
            self.segmentEditorWidget.setSourceVolumeNode(self.masterVolumeNode)
            # Add segment and select
            self.segmentId = self.segmentationNode.GetSegmentation().AddEmptySegment("Segmentation")
            self.segmentEditorWidget.setCurrentSegmentID(self.segmentId)



    def clearSegment(self):
        if self.BeforeSegmentationNode:
            self.segmentEditorWidget.setSegmentationNode(self.BeforeSegmentationNode)
            self.segmentEditorWidget.setSourceVolumeNode(self.masterVolumeNode)
            slicer.mrmlScene.RemoveNode(self.segmentationNode)
            # Delete exportFolderItemId
        else:
            slicer.mrmlScene.RemoveNode(self.segmentationNode)
        # Delete exportFolderItemId
        shNode = slicer.mrmlScene.GetSubjectHierarchyNode()
        
        # Find folder named "Segments"
        folderItems = vtk.vtkIdList()
        shNode.GetItemChildren(shNode.GetSceneItemID(), folderItems, True)
        for i in range(folderItems.GetNumberOfIds()):
            itemId = folderItems.GetId(i)
            itemName = shNode.GetItemName(itemId)
            if itemName == "exportFromSegments":
                # Find and delete the folder (including all model sub-items)
                shNode.RemoveItem(itemId)
                print("Deleted exported model folder")
                break

    # Threshold segmentation
    def thresholdSegment(self, lowerThreshold, upperThreshold):
        self.segmentEditorWidget.setActiveEffectByName("Threshold")
        effect = self.segmentEditorWidget.activeEffect()
        effect.setParameter("MinimumThreshold", str(lowerThreshold))
        effect.setParameter("MaximumThreshold", str(upperThreshold))
        effect.self().onApply()

    # Split into multiple small islands
    def splitIslands(self):
        self.segmentEditorWidget.setActiveEffectByName("Islands")
        effect = self.segmentEditorWidget.activeEffect()
        effect.setParameter("Operation", "SPLIT_ISLANDS_TO_SEGMENTS")
        effect.setParameter("MinimumSize", "1000")
        effect.self().onApply()

    # Delete the segment with the most voxels in segmentation
    def removeLargestSegment(self):
        """
        Delete the segment with the most voxels in segmentation
        
        Returns:
        removedSegmentID: ID of the deleted segment
        """
        if not self.segmentationNode:
            print("Segmentation node not found")
            return None
        
        # Get all segment IDs
        segmentIDs = vtk.vtkStringArray()
        self.segmentationNode.GetSegmentation().GetSegmentIDs(segmentIDs)
        
        largestSegmentID = None
        maxVoxelCount = -1
        
        # Iterate through all segments to find the one with the most voxels
        for i in range(segmentIDs.GetNumberOfValues()):
            segmentID = segmentIDs.GetValue(i)
            
            # Get binary labelmap representation of segment
            segmentLabelmap = slicer.vtkOrientedImageData()
            slicer.vtkSlicerSegmentationsModuleLogic.GetSegmentBinaryLabelmapRepresentation(
                self.segmentationNode, segmentID, segmentLabelmap)
            
            # Calculate number of non-zero voxels
            voxelCount = 0
            if segmentLabelmap:
                voxelCount = vtk.vtkImageAccumulate()
                voxelCount.SetInputData(segmentLabelmap)
                voxelCount.Update()
                # Get number of non-zero voxels
                voxelCount = int(voxelCount.GetVoxelCount() - voxelCount.GetOutput().GetScalarComponentAsDouble(0, 0, 0, 0))
            
            segmentName = self.segmentationNode.GetSegmentation().GetSegment(segmentID).GetName()
            print(f"Segment {segmentName} contains {voxelCount} voxels")
            
            # Update max voxel count and corresponding segment
            if voxelCount > maxVoxelCount:
                maxVoxelCount = voxelCount
                largestSegmentID = segmentID
        
        # Delete segment with the most voxels
        if largestSegmentID:
            segmentName = self.segmentationNode.GetSegmentation().GetSegment(largestSegmentID).GetName()
            print(f"Deleted segment with most voxels: {segmentName}, voxel count: {maxVoxelCount}")
            self.segmentationNode.GetSegmentation().RemoveSegment(largestSegmentID)
            return largestSegmentID
        else:
            print("No segment found to delete")
            return None

    # Convert all segments in segmentation to models
    def convertSegmentsToModels(self):
        """
        Convert all segments in segmentation to models
        
        Returns:
        modelNodes: List of generated model nodes
        """
        if not self.segmentationNode:
            print("Segmentation node not found")
            return []
        shNode = slicer.mrmlScene.GetSubjectHierarchyNode()
        exportFolderItemId = shNode.CreateFolderItem(shNode.GetSceneItemID(), "exportFromSegments")
        slicer.modules.segmentations.logic().ExportAllSegmentsToModels(self.segmentationNode, exportFolderItemId)
        # Correctly get all nodes in the folder
        modelNodes = []
        # Create vtk ID list to store sub-item IDs
        childItemIds = vtk.vtkIdList()
        # Get all sub-items of the folder
        shNode.GetItemChildren(exportFolderItemId, childItemIds)
        
        # Iterate through all sub-items
        for i in range(childItemIds.GetNumberOfIds()):
            # Get sub-item ID
            childItemId = childItemIds.GetId(i)
            # Get corresponding node by sub-item ID
            modelNode = shNode.GetItemDataNode(childItemId)
            if modelNode:
                modelNodes.append(modelNode)
                print(f"Exported model: {modelNode.GetName()}")

        print(f"Exported {len(modelNodes)} models in total")
        return modelNodes
    
    # Compute bounds of the given model
    def computeModelBounds(self, modelNode):
        """
        Compute bounds of the given model
        
        Parameters:
        modelNode: Model node
        
        Returns:
        bounds: Bounds of the model
        """
        if not modelNode:
            print("未找到Model node")
            return None
        
        polyData = modelNode.GetPolyData()
        if not polyData:
            print("Model node没有PolyData")
            return None
        
        bounds = [0, 0, 0, 0, 0, 0]
        polyData.GetBounds(bounds)
        
        return bounds
        
    def fitPlaneToPolyData(self, polyData):
        """
        Fit all points on polydata to a plane, compute normal vector and point on plane
        
        Parameters:
        polyData: vtkPolyData object
        
        Returns:
        normal: Plane normal vector, normalized unit vector
        point: Point on plane (centroid)
        avg_distance: Average distance of all points to the plane
        std_distance: Standard deviation of distances
        """
        if not polyData:
            print("Invalid PolyData")
            return None, None, None, None
        
        # Get number of points
        numPoints = polyData.GetNumberOfPoints()
        if numPoints == 0:
            print("PolyData contains no points")
            return None, None, None, None
        
        # Collect coordinates of all points
        import numpy as np
        points = np.zeros((numPoints, 3))
        for i in range(numPoints):
            point = polyData.GetPoint(i)
            points[i] = point
        
        # Compute difference between min and max values in Z coordinate system
        z_range = np.max(points[:, 2]) - np.min(points[:, 2])
        if z_range < 80 :
            print(f"Z coordinate range unreasonable: {z_range:.4f}")
            return None, None, None, None

        # Compute centroid
        centroid = np.mean(points, axis=0)
        
        # Center the point cloud
        centered_points = points - centroid
        
        # Compute covariance matrix
        cov_matrix = np.dot(centered_points.T, centered_points) / numPoints
        
        # Compute eigenvalues and eigenvectors
        eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)
        
        # Eigenvector corresponding to the smallest eigenvalue is the normal vector
        normal = eigenvectors[:, 0]
        
        # Ensure normal points outwards (can be adjusted according to the actual situation of the medical headframe)
        # Assuming z-direction should be positive here
        if normal[2] < 0:
            normal = -normal
        
        # Normalize normal vector
        normal = normal / np.linalg.norm(normal)
        
        print(f"Fitted plane - Normal vector: {normal}, Plane point: {centroid}")

        # 计算Average distance of all points to the plane
        distances = np.abs(np.dot(centered_points, normal))
        avg_distance = np.mean(distances)
        std_distance = np.std(distances)
        max_distance = np.max(distances)
        
        print(f"Distance of points to plane - Average: {avg_distance:.4f}, Std dev: {std_distance:.4f}, Max: {max_distance:.4f}")
        
        # Evaluate plane fitting quality - Compute fitting error (std dev / average)
        fit_quality = std_distance / (avg_distance if avg_distance > 1e-10 else 1e-10)
        print(f"Plane fitting quality (smaller is better): {fit_quality:.4f}")

        if fit_quality > 2:
            return None, None, None, None
        


        
        return normal, centroid, avg_distance, std_distance
    def createFrameModel(self, fromPoints, radius=0.5):
        """
        Create a tube frame model from the four provided points
        
        Parameters:
        fromPoints: numpy array containing four point coordinates (4x3)
        radius: Tube radius, default 0.5
        
        返回:
        frameModelNode: Created frame model
        """
        import vtk
        
        # Create points and lines
        points = vtk.vtkPoints()
        lines = vtk.vtkCellArray()
        
        # Add points
        for i in range(4):
            points.InsertPoint(i, fromPoints[i])
        
        # Create line segments (connected in specific order)
        # 0-1, 1-3, 3-2, 2-0 form a closed rectangle
        lineIndices = [[0,1], [1,2], [2,3]]
        
        for lineIdx in lineIndices:
            line = vtk.vtkLine()
            line.GetPointIds().SetId(0, lineIdx[0])
            line.GetPointIds().SetId(1, lineIdx[1])
            lines.InsertNextCell(line)
        
        # Create polyData
        polyData = vtk.vtkPolyData()
        polyData.SetPoints(points)
        polyData.SetLines(lines)
        
        # Use tube filter to convert line segments to cylinders
        tubeFilter = vtk.vtkTubeFilter()
        tubeFilter.SetInputData(polyData)
        tubeFilter.SetRadius(radius)
        tubeFilter.SetNumberOfSides(16)  # Control smoothness of cylinder
        tubeFilter.CappingOn()  # Cap ends of tube
        tubeFilter.Update()
        

        return tubeFilter.GetOutput()

    # Get corner points through shape analysis
    def getCornerPoint(self, modelNode):
        # Get all points of the model
        polyData = modelNode.GetPolyData()
        numPoints = polyData.GetNumberOfPoints()
        points = np.zeros((numPoints, 3))
        for i in range(numPoints):
            point = polyData.GetPoint(i)
            points[i] = point

        if "behind" in modelNode.GetName():
            # Get median of X coordinates
            X_middle = (np.min(points[:, 0])+np.max(points[:, 0]))/2
            # Get points with X coordinate less than X_middle
            left_points = points[points[:, 0] < X_middle]
            # Get point with max Z in left_points
            left_max_point = left_points[np.argmax(left_points[:, 2])]
            # Get point with min Z in left_points
            left_min_point = left_points[np.argmin(left_points[:, 2])]
            # Get points with X coordinate greater than X_middle
            right_points = points[points[:, 0] > X_middle]
            # Get point with max Z in right_points
            right_max_point = right_points[np.argmax(right_points[:, 2])]
            # Get point with min Z in right_points
            right_min_point = right_points[np.argmin(right_points[:, 2])]
            return left_max_point, left_min_point, right_max_point, right_min_point
        else:
            # Get median of Y coordinates
            Y_middle = (np.min(points[:, 1])+np.max(points[:, 1]))/2
            # Get points with Y coordinate less than Y_middle
            behind_points = points[points[:, 1] < Y_middle]
            # Get point with max Z in behind_points
            behind_max_point = behind_points[np.argmax(behind_points[:, 2])]
            # Get point with min Z in behind_points
            behind_min_point = behind_points[np.argmin(behind_points[:, 2])]
            # Get points with Y coordinate greater than Y_middle
            back_points = points[points[:, 1] > Y_middle]
            # Get point with max Z in back_points
            back_max_point = back_points[np.argmax(back_points[:, 2])]
            # Get point with min Z in back_points
            back_min_point = back_points[np.argmin(back_points[:, 2])]
            return behind_max_point, behind_min_point, back_max_point, back_min_point
        
    # Identify frame
    def identifyFrame(self, NInfoList):
        """
        Identify headframe, return the uppermost points
        """
        returnList =[] 

        # Sort by X coordinate
        x_sorted = sorted(NInfoList, key=lambda item: item[2][0])  # Sort by point's x coordinate
        
        # Sort by Y coordinate
        y_sorted = sorted(NInfoList, key=lambda item: item[2][1])  # Sort by point's y coordinate
        
        # Mark left plane (min X coordinate)
        left_plane = x_sorted[0]
        left_plane[0].SetName("left_plane")
        print(f"Left plane - Position: {left_plane[2]}, Normal: {left_plane[1]}")
        # Get target points
        targetPoints = myHeadFrameRegistration.getCornerPoint(left_plane[0])
        # Create markupsFiducial node
        markupsFiducialNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode")
        markupsFiducialNode.CreateDefaultDisplayNodes()
        markupsFiducialNode.SetName("left_Points")
        # Add points
        for i in range(4):
            markupsFiducialNode.AddControlPoint(targetPoints[i])

        returnList.append([targetPoints[0],targetPoints[2]])
        # Mark right plane (max X coordinate)
        right_plane = x_sorted[2]
        right_plane[0].SetName("right_plane")
        print(f"Right plane - Position: {right_plane[2]}, Normal: {right_plane[1]}")
        # Get target points
        targetPoints = myHeadFrameRegistration.getCornerPoint(right_plane[0])
        # Create markupsFiducial node
        markupsFiducialNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode")
        markupsFiducialNode.CreateDefaultDisplayNodes()
        markupsFiducialNode.SetName("right_Points")
        # Add points
        for i in range(4):
            markupsFiducialNode.AddControlPoint(targetPoints[i])
        returnList.append([targetPoints[0],targetPoints[2]])
        if len(NInfoList) == 3:
            # Mark anterior plane (max Y coordinate)
            anterior_plane = y_sorted[-1]
            anterior_plane[0].SetName("behind_plane")
            print(f"Anterior plane - Position: {anterior_plane[2]}, Normal: {anterior_plane[1]}")
            # Get target points
            targetPoints = myHeadFrameRegistration.getCornerPoint(anterior_plane[0])
            # Create markupsFiducial node
            markupsFiducialNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode")
            markupsFiducialNode.CreateDefaultDisplayNodes()
            markupsFiducialNode.SetName("behind_Points")
            # Add points
            for i in range(4):
                markupsFiducialNode.AddControlPoint(targetPoints[i])
            returnList.append([targetPoints[0],targetPoints[2]])
            
        return returnList
