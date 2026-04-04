# Manual Basic Operation Guide for BrainStereo
## 1. Program Download and Installation
### 1.1 Download and Install the Latest Version of 3D Slicer
- Download the software from [https://download.slicer.org](https://download.slicer.org).
- If you're new to 3D Slicer, it's recommended to explore its basic features. The official website provides comprehensive resources, and an active community can assist with any questions or challenges.

|Operating System|Stable Release|Preview Release|
|---|---|---|
|Windows|5.8.1 (built 2025-03-03 revision 33241)|5.9.0 (built 2025-05-01 revision 33626)|
|macOs|5.8.1 (built 2025-03-03 revision 33241)|5.9.0 (built 2025-05-01 revision 33626)|
|Linux|5.8.1 (built 2025-03-03 revision 33241)|5.9.0 (built 2025-05-01 revision 33626)|

### 1.2 Download the BrainStereo module
- Download the BrainStereo module from the repository: [https://github.com/xmszj/BrainStereo](https://github.com/xmszj/BrainStereo).
- After extraction, place the entire module folder into a fixed directory. It's advisable to put it within the 3D Slicer installation path for easy access.
- The module includes the main algorithm script “BrainStereo.py” and a “Resources” folder with essential files like the frame model and sample CT datasets. Ensure the folder structure is as follows:
```
bin
Resources
BrainStereo
    BrainStereo.py
include
lib
libexec
share
slicer.org
.slicerrc.py
Slicer.exe
Uninstall.exe
```

### 1.3 Register the BrainStereo module in 3D Slicer
- Double-click `Slicer.exe` to launch 3D Slicer.
- Navigate to `Edit` -> `Application Settings` -> `Modules`.
- In the `Additional module paths` section, click the `Add` button and add the path of the BrainStereo module directory.
- Restart 3D Slicer to complete the module registration.

## 2. Module Usage
### 2.1 Launch the BrainStereo module
- In the module search bar of 3D Slicer, type “brain” and double-click “BrainStereo” to open the program's main interface.

### 2.2 Load and view the CT test dataset
- In the main interface, click the `Test` button to load the pre-stored CT test dataset.
- After the data is loaded, click the `Show 3D` button to automatically render and display the current CT in the 3D view.
- The green area (`Workflow`) is for head frame registration, the purple area (`Result`) shows computational results, and the yellow area (`Visualization`) is for 3D visualization.

### 2.3 Operate within the Workflow section
- **Step 1: Mark Points**: Click on `Step 1: Mark Points` in the `Workflow` section. Then, mark the four points of the N-shaped reference board in the current axial view. The marking order doesn't matter. The software will automatically recognize the points as a, b, c, and d and correct their positions.
- **Step 2: Auto Align**: After completing Step 1, click on `Step 2: Auto Align` to perform head frame registration calculation. The displayed RMSE (Root Mean Square Error) represents the registration accuracy in millimeters. Click `Visualize Plan` to check the registration accuracy between the current CT data and the reference head frame.
- **Step 3: Set Target and Entry Point**: Adjust the CT data's contrast or slice level to identify the surgical target location. Click `Step 3: Set Target` to place the target marker, and then place the entry point marker in the same way. Click `Visualize Plan` to synchronize the head frame model to the current position. If needed, drag the markers to reposition the target or entry point.

## 3. Other Functions
- After completing the above steps, frame registration, target and entry point selection, and result calculation can be completed quickly.
- To add multiple surgical paths, after selecting a pair of target and entry points, click `New Plan` to place a simulated path model.
- Users can manually adjust the head frame penetration direction by clicking different sliders in the `Visualization` area to simulate various surgical approaches. 
