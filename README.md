# Manual Basic Operation Guide for ATStereo

## 1. Program Download and Installation

### 1.1 Download and Install the Latest Version of 3D Slicer

* Download the software from [https://download.slicer.org](https://download.slicer.org).
* If you're new to 3D Slicer, it's recommended to explore its basic features. The official website provides comprehensive resources, and an active community can assist with any questions or challenges.

| Operating System | Stable Release | Preview Release |
| --- | --- | --- |
| **Windows** | 5.12.3 (built 2026-07-23 revision 34627) | 5.13.0 (built 2026-08-18 revision 34906) |
| **macOS** | 5.12.3 (built 2026-07-23 revision 34627) | 5.13.0 (built 2026-08-18 revision 34906) |
| **Linux** | 5.12.3 (built 2026-07-23 revision 34627) | 5.13.0 (built 2026-08-18 revision 34906) |

### 1.2 Download the ATStereo module

* Download the ATStereo module from the repository: [https://github.com/taha-at/ATstereo](https://github.com/taha-at/ATstereo).
* After extraction, place the entire module folder into a fixed directory. It's advisable to put it within the 3D Slicer installation path for easy access.
* The module includes the main algorithm script `ATStereo.py`, the user interface `ATStereo.ui`, and a `Resources` folder containing essential files like the patented frame models and sample CT dataset. Ensure the folder structure is as follows:

```text
bin
Resources
ATStereo
    ATStereo.py
include
lib
libexec
share
slicer.org
.slicerrc.py
Slicer.exe
Uninstall.exe

```

### 1.3 Register the ATStereo module in 3D Slicer

* Double-click `Slicer.exe` to launch 3D Slicer.
* Navigate to **Edit** -> **Application Settings** -> **Modules**.
* In the `Additional module paths` section, click the **Add** button and add the path of the ATStereo module directory.
* Restart 3D Slicer to complete the module registration.

---

## 2. Module Usage

### 2.1 Launch the ATStereo module

* In the module search bar of 3D Slicer, type "ATStereo" and double-click it to open the program's main interface.

### 2.2 Load and view the CT dataset

* **Importing Data:** Use the **Browse Files** or **Browse Folder** buttons in the `Data Import` section to load your NIfTI files (`.nii` or `.nii.gz`). The module will automatically skip duplicate volumes. Moreover, you can add any DICOM dataset using the Add DICOM Data module from 3D Slicer built-in modules (Top dropdown bar -> Add DICOM Data) or from the main page.
* **Test Data:** Alternatively, click the **Test** button to load the pre-stored CT test dataset.
* **3D Rendering:** After the data is loaded, click the **Show 3D** button to automatically render and display the current volume in the 3D view.
* **Interface Layout:** The interface is divided into functional blocks: `Data Import`, `Frame` parameters, `Mechanism`, `Workflow` for registration and planning, `Result` for kinematics, `Data Probe` for real-time coordinates, and `Visualization` for 3D frame simulation.

### 2.3 Operate within the Workflow section

* **Step 1: Pick 4 points:** Click on `Step 1: Pick 4 points` in the `Workflow` section. You must place exactly four points in the 3D or slice views in this **exact** order to define the frame geometry:
1. Left Isocenter
2. Right Isocenter
3. Left point at (0,0,120)
4. Right point at (0,0,120)


* **Step 2: Align to Isocenters:** After placing all four points, click `Step 2: Align to Isocenters` to perform rigid body registration. A pop-up will confirm the alignment, and the displayed RMSE (Root Mean Square Error) represents the registration accuracy in millimeters.
* **Steps 3 & 4: Left Trajectory Planning:** Click `Step 3: Set Left Target` to place the target marker for the left hemisphere, followed by `Step 4: Set Left Entry` to place the corresponding entry point.
* **Steps 5 & 6: Right Trajectory Planning:** Click `Step 5: Set Right Target` and `Step 6: Set Right Entry` to plan the trajectory for the right hemisphere.
* **Visualize Plan:** Click **Visualize Plan** to synchronize the dual stereotactic frame models to your planned trajectories. If needed, drag the markers in the slice views to fine-tune the target or entry points; the frame will automatically update.

---

## 3. Advanced Functions & Analysis

* **Bilateral Kinematics:** Unlike standard single-arc systems, ATStereo simultaneously computes trajectory kinematics for both the left and right sides. The final Local X, Y, Z coordinates, as well as the Arc and Ring angles for each hemisphere, are displayed side-by-side in the `Result` section.
* **Real-Time Data Probe:** Hover your mouse over the 3D view to activate the Data Probe. It will automatically detect which hemisphere you are pointing at and output the real-time stereotactic coordinates (X, Y, Z) relative to that side's isocenter in the `Data Probe` panel.
* **Surgical Simulation:** Users can manually override and adjust the head frame penetration direction by using the linear sliders in the `Visualization` area. You can independently tweak the Local X, Y, Z, Arc, and Ring values for the Left Side and Right Side to simulate varying surgical approaches.
* **Trajectory Separation Warning:** The system runs an automated check in the background. If your planned left and right trajectories are dangerously close to one another (under 5.0 mm), a warning will display to prevent potential hardware collision during bilateral procedures.
* **New Plans:** To add multiple simulated paths, click the **New Plan** button to lock in your current trajectories and duplicate the tube models for visual reference.