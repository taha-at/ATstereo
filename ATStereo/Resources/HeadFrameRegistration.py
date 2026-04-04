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
            # 添加分段并选中
            self.segmentId = self.segmentationNode.GetSegmentation().AddEmptySegment("Segmentation")
            self.segmentEditorWidget.setCurrentSegmentID(self.segmentId)



    def clearSegment(self):
        if self.BeforeSegmentationNode:
            self.segmentEditorWidget.setSegmentationNode(self.BeforeSegmentationNode)
            self.segmentEditorWidget.setSourceVolumeNode(self.masterVolumeNode)
            slicer.mrmlScene.RemoveNode(self.segmentationNode)
            # 删除exportFolderItemId
        else:
            slicer.mrmlScene.RemoveNode(self.segmentationNode)
        # 删除exportFolderItemId
        shNode = slicer.mrmlScene.GetSubjectHierarchyNode()
        
        # 查找名为"Segments"的文件夹
        folderItems = vtk.vtkIdList()
        shNode.GetItemChildren(shNode.GetSceneItemID(), folderItems, True)
        for i in range(folderItems.GetNumberOfIds()):
            itemId = folderItems.GetId(i)
            itemName = shNode.GetItemName(itemId)
            if itemName == "exportFromSegments":
                # 找到并删除该文件夹(包含所有模型子项)
                shNode.RemoveItem(itemId)
                print("已删除导出的模型文件夹")
                break

    # 阈值分割
    def thresholdSegment(self, lowerThreshold, upperThreshold):
        self.segmentEditorWidget.setActiveEffectByName("Threshold")
        effect = self.segmentEditorWidget.activeEffect()
        effect.setParameter("MinimumThreshold", str(lowerThreshold))
        effect.setParameter("MaximumThreshold", str(upperThreshold))
        effect.self().onApply()

    # 分割为多个小岛屿
    def splitIslands(self):
        self.segmentEditorWidget.setActiveEffectByName("Islands")
        effect = self.segmentEditorWidget.activeEffect()
        effect.setParameter("Operation", "SPLIT_ISLANDS_TO_SEGMENTS")
        effect.setParameter("MinimumSize", "1000")
        effect.self().onApply()

    # 删除segmentation内体素数量最多的segment
    def removeLargestSegment(self):
        """
        删除segmentation内体素数量最多的segment
        
        返回：
        removedSegmentID: 被删除的segment的ID
        """
        if not self.segmentationNode:
            print("未找到分割节点")
            return None
        
        # 获取所有segment IDs
        segmentIDs = vtk.vtkStringArray()
        self.segmentationNode.GetSegmentation().GetSegmentIDs(segmentIDs)
        
        largestSegmentID = None
        maxVoxelCount = -1
        
        # 遍历所有segment找出体素数量最多的
        for i in range(segmentIDs.GetNumberOfValues()):
            segmentID = segmentIDs.GetValue(i)
            
            # 获取segment的二进制标签映射表示
            segmentLabelmap = slicer.vtkOrientedImageData()
            slicer.vtkSlicerSegmentationsModuleLogic.GetSegmentBinaryLabelmapRepresentation(
                self.segmentationNode, segmentID, segmentLabelmap)
            
            # 计算非零体素数量
            voxelCount = 0
            if segmentLabelmap:
                voxelCount = vtk.vtkImageAccumulate()
                voxelCount.SetInputData(segmentLabelmap)
                voxelCount.Update()
                # 获取非零体素的数量
                voxelCount = int(voxelCount.GetVoxelCount() - voxelCount.GetOutput().GetScalarComponentAsDouble(0, 0, 0, 0))
            
            segmentName = self.segmentationNode.GetSegmentation().GetSegment(segmentID).GetName()
            print(f"Segment {segmentName} 包含 {voxelCount} 个体素")
            
            # 更新最大体素数量及对应的segment
            if voxelCount > maxVoxelCount:
                maxVoxelCount = voxelCount
                largestSegmentID = segmentID
        
        # 删除体素数量最多的segment
        if largestSegmentID:
            segmentName = self.segmentationNode.GetSegmentation().GetSegment(largestSegmentID).GetName()
            print(f"删除体素数量最多的segment: {segmentName}，体素数量: {maxVoxelCount}")
            self.segmentationNode.GetSegmentation().RemoveSegment(largestSegmentID)
            return largestSegmentID
        else:
            print("未找到需要删除的segment")
            return None

    # 将segmentation内所有的segment转为model
    def convertSegmentsToModels(self):
        """
        将segmentation内所有的segment转换为model
        
        返回：
        modelNodes: 生成的模型节点列表
        """
        if not self.segmentationNode:
            print("未找到分割节点")
            return []
        shNode = slicer.mrmlScene.GetSubjectHierarchyNode()
        exportFolderItemId = shNode.CreateFolderItem(shNode.GetSceneItemID(), "exportFromSegments")
        slicer.modules.segmentations.logic().ExportAllSegmentsToModels(self.segmentationNode, exportFolderItemId)
        # 正确获取文件夹中的所有节点
        modelNodes = []
        # 创建vtk ID列表用于存储子项目ID
        childItemIds = vtk.vtkIdList()
        # 获取文件夹的所有子项目
        shNode.GetItemChildren(exportFolderItemId, childItemIds)
        
        # 遍历所有子项目
        for i in range(childItemIds.GetNumberOfIds()):
            # 获取子项目ID
            childItemId = childItemIds.GetId(i)
            # 通过子项目ID获取对应的节点
            modelNode = shNode.GetItemDataNode(childItemId)
            if modelNode:
                modelNodes.append(modelNode)
                print(f"导出模型: {modelNode.GetName()}")

        print(f"共导出 {len(modelNodes)} 个模型")
        return modelNodes
    
    # 计算所给模型的bounds
    def computeModelBounds(self, modelNode):
        """
        计算所给模型的bounds
        
        参数：
        modelNode: 模型节点
        
        返回：
        bounds: 模型的bounds
        """
        if not modelNode:
            print("未找到模型节点")
            return None
        
        polyData = modelNode.GetPolyData()
        if not polyData:
            print("模型节点没有PolyData")
            return None
        
        bounds = [0, 0, 0, 0, 0, 0]
        polyData.GetBounds(bounds)
        
        return bounds
        
    def fitPlaneToPolyData(self, polyData):
        """
        拟合polydata上所有点到平面，计算法向量及平面上的点
        
        参数：
        polyData: vtkPolyData对象
        
        返回：
        normal: 平面法向量，归一化的单位向量
        point: 平面上的点（质心）
        avg_distance: 所有点到平面的平均距离
        std_distance: 距离的标准差
        """
        if not polyData:
            print("无效的PolyData")
            return None, None, None, None
        
        # 获取点数
        numPoints = polyData.GetNumberOfPoints()
        if numPoints == 0:
            print("PolyData不包含点")
            return None, None, None, None
        
        # 收集所有点的坐标
        import numpy as np
        points = np.zeros((numPoints, 3))
        for i in range(numPoints):
            point = polyData.GetPoint(i)
            points[i] = point
        
        # 计算Z坐标系最小及最大值的差值
        z_range = np.max(points[:, 2]) - np.min(points[:, 2])
        if z_range < 80 :
            print(f"Z坐标范围不合理: {z_range:.4f}")
            return None, None, None, None

        # 计算质心
        centroid = np.mean(points, axis=0)
        
        # 点云中心化
        centered_points = points - centroid
        
        # 计算协方差矩阵
        cov_matrix = np.dot(centered_points.T, centered_points) / numPoints
        
        # 计算特征值和特征向量
        eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)
        
        # 最小特征值对应的特征向量即为法向量
        normal = eigenvectors[:, 0]
        
        # 确保法向量指向外部（可根据医学头架的实际情况调整）
        # 这里假设z方向应为正向
        if normal[2] < 0:
            normal = -normal
        
        # 归一化法向量
        normal = normal / np.linalg.norm(normal)
        
        print(f"拟合平面 - 法向量: {normal}, 平面点: {centroid}")

        # 计算所有点到平面的平均距离
        distances = np.abs(np.dot(centered_points, normal))
        avg_distance = np.mean(distances)
        std_distance = np.std(distances)
        max_distance = np.max(distances)
        
        print(f"点到平面的距离 - 平均值: {avg_distance:.4f}, 标准差: {std_distance:.4f}, 最大值: {max_distance:.4f}")
        
        # 评估平面拟合质量 - 计算拟合误差(标准差/平均值)
        fit_quality = std_distance / (avg_distance if avg_distance > 1e-10 else 1e-10)
        print(f"平面拟合质量(越小越好): {fit_quality:.4f}")

        if fit_quality > 2:
            return None, None, None, None
        


        
        return normal, centroid, avg_distance, std_distance
    def createFrameModel(self, fromPoints, radius=0.5):
        """
        从提供的四个点创建一个管道框架模型
        
        参数：
        fromPoints: 包含四个点坐标的numpy数组(4x3)
        radius: 管道半径，默认为0.5
        
        返回:
        frameModelNode: 创建的框架模型
        """
        import vtk
        
        # 创建点和线
        points = vtk.vtkPoints()
        lines = vtk.vtkCellArray()
        
        # 添加点
        for i in range(4):
            points.InsertPoint(i, fromPoints[i])
        
        # 创建线段（按特定顺序连接）
        # 0-1, 1-3, 3-2, 2-0 形成一个闭合矩形
        lineIndices = [[0,1], [1,2], [2,3]]
        
        for lineIdx in lineIndices:
            line = vtk.vtkLine()
            line.GetPointIds().SetId(0, lineIdx[0])
            line.GetPointIds().SetId(1, lineIdx[1])
            lines.InsertNextCell(line)
        
        # 创建polyData
        polyData = vtk.vtkPolyData()
        polyData.SetPoints(points)
        polyData.SetLines(lines)
        
        # 使用管道过滤器将线段转换为圆柱体
        tubeFilter = vtk.vtkTubeFilter()
        tubeFilter.SetInputData(polyData)
        tubeFilter.SetRadius(radius)
        tubeFilter.SetNumberOfSides(16)  # 控制圆柱体的平滑度
        tubeFilter.CappingOn()  # 封闭管道两端
        tubeFilter.Update()
        

        return tubeFilter.GetOutput()

    # 通过形状分析获取角点
    def getCornerPoint(self, modelNode):
        # 获取模型的所有点
        polyData = modelNode.GetPolyData()
        numPoints = polyData.GetNumberOfPoints()
        points = np.zeros((numPoints, 3))
        for i in range(numPoints):
            point = polyData.GetPoint(i)
            points[i] = point

        if "behind" in modelNode.GetName():
            # 获取X坐标中值
            X_middle = (np.min(points[:, 0])+np.max(points[:, 0]))/2
            # 获取所有点中X坐标小于X_middle的点
            left_points = points[points[:, 0] < X_middle]
            # 获取left_points中Z最大点
            left_max_point = left_points[np.argmax(left_points[:, 2])]
            # 获取left_points中Z最小点
            left_min_point = left_points[np.argmin(left_points[:, 2])]
            # 获取所有点中X坐标大于X_middle的点
            right_points = points[points[:, 0] > X_middle]
            # 获取right_points中Z最大点
            right_max_point = right_points[np.argmax(right_points[:, 2])]
            # 获取right_points中Z最小点
            right_min_point = right_points[np.argmin(right_points[:, 2])]
            return left_max_point, left_min_point, right_max_point, right_min_point
        else:
            # 获取Y坐标中值
            Y_middle = (np.min(points[:, 1])+np.max(points[:, 1]))/2
            # 获取所有点中Y坐标小于Y_middle的点
            behind_points = points[points[:, 1] < Y_middle]
            # 获取behind_points中Z最大点
            behind_max_point = behind_points[np.argmax(behind_points[:, 2])]
            # 获取behind_points中Z最小点
            behind_min_point = behind_points[np.argmin(behind_points[:, 2])]
            # 获取所有点中Y坐标大于Y_middle的点
            back_points = points[points[:, 1] > Y_middle]
            # 获取back_points中Z最大点
            back_max_point = back_points[np.argmax(back_points[:, 2])]
            # 获取back_points中Z最小点
            back_min_point = back_points[np.argmin(back_points[:, 2])]
            return behind_max_point, behind_min_point, back_max_point, back_min_point
        
    # 识别支架
    def identifyFrame(self, NInfoList):
        """
        识别头架,返回最上层的点位
        """
        returnList =[] 

        # 按X坐标排序
        x_sorted = sorted(NInfoList, key=lambda item: item[2][0])  # 按点的x坐标排序
        
        # 按Y坐标排序
        y_sorted = sorted(NInfoList, key=lambda item: item[2][1])  # 按点的y坐标排序
        
        # 标记左侧平面 (X坐标最小)
        left_plane = x_sorted[0]
        left_plane[0].SetName("left_plane")
        print(f"左侧平面 - 位置: {left_plane[2]}, 法向量: {left_plane[1]}")
        # 获取目标点位
        targetPoints = myHeadFrameRegistration.getCornerPoint(left_plane[0])
        # 创建markupsFiducial节点
        markupsFiducialNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode")
        markupsFiducialNode.CreateDefaultDisplayNodes()
        markupsFiducialNode.SetName("left_Points")
        # 添加点
        for i in range(4):
            markupsFiducialNode.AddControlPoint(targetPoints[i])

        returnList.append([targetPoints[0],targetPoints[2]])
        # 标记右侧平面 (X坐标最大)
        right_plane = x_sorted[2]
        right_plane[0].SetName("right_plane")
        print(f"右侧平面 - 位置: {right_plane[2]}, 法向量: {right_plane[1]}")
        # 获取目标点位
        targetPoints = myHeadFrameRegistration.getCornerPoint(right_plane[0])
        # 创建markupsFiducial节点
        markupsFiducialNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode")
        markupsFiducialNode.CreateDefaultDisplayNodes()
        markupsFiducialNode.SetName("right_Points")
        # 添加点
        for i in range(4):
            markupsFiducialNode.AddControlPoint(targetPoints[i])
        returnList.append([targetPoints[0],targetPoints[2]])
        if len(NInfoList) == 3:
            # 标记前侧平面 (Y坐标最大)
            anterior_plane = y_sorted[-1]
            anterior_plane[0].SetName("behind_plane")
            print(f"前侧平面 - 位置: {anterior_plane[2]}, 法向量: {anterior_plane[1]}")
            # 获取目标点位
            targetPoints = myHeadFrameRegistration.getCornerPoint(anterior_plane[0])
            # 创建markupsFiducial节点
            markupsFiducialNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode")
            markupsFiducialNode.CreateDefaultDisplayNodes()
            markupsFiducialNode.SetName("behind_Points")
            # 添加点
            for i in range(4):
                markupsFiducialNode.AddControlPoint(targetPoints[i])
            returnList.append([targetPoints[0],targetPoints[2]])
            
        return returnList
