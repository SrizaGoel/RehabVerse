# RehabVerse — Features Summary

RehabVerse is an interactive rehabilitation suite designed for upper limb recovery (specifically rotator cuff rehabilitation). Using AI-powered pose tracking (MediaPipe) and real-time feedback, patients can perform exercises safely and track their recovery progress.

Below is an overview of the modules and features implemented in the system:

---

## 1. Side Arm Raise (`side_arm_raise.py`)
* **Objective**: A fundamental range of motion (ROM) and repetition tracker for shoulder abduction and flexion.
* **Core Features**:
  - **Dual-Arm Tracking**: Automatically detects and tracks both Left and Right arms.
  - **Live ROM Meter**: Displays current elevation angle in real-time.
  - **Rep Counter**: Counts completed reps with clear "UP" and "DOWN" stage indicators.
  - **Recovery Milestones**: Maps ROM to functional daily achievements (e.g. *Reach Table Height*, *Comb Your Hair*, *Reach Overhead Shelf*).
  - **Smoothing & Visbility Checks**: Employs rolling median filters to eliminate noise and warns the user if their body is obscured.

---

## 2. The Forgotten Orchestra (`forgotten_orchestra.py`)
* **Objective**: Gamified recovery where lateral arm abduction dynamically conducts a virtual symphony.
* **Core Features**:
  - **Weekly Milestone Scaling**: Goals adapt to your rehab week (Week 1–6+). Unlock thresholds scale so you never push beyond your safe limits.
  - **Interactive Sound Engine**: Synthesizes notes and chords in real-time (using pygame & numpy) across 6 layers (Triangle, Flute, Violin, Cello, Choir, Orchestra).
  - **Progress Dashboard**: Tracks reps, hold durations, and overall music restoration percentage.
  - **Visualizer Bars**: A custom graphical soundboard scales and animates matching the volume of each active instrument.

---

## 3. Paint the Sky (`paint_the_sky.py`)
* **Objective**: A weekly mobility challenge where the user "paints" templates by holding their arm raised.
* **Core Features**:
  - **Weekly Lock System**: The challenge is locked until cumulative weekly targets are met (e.g. 60 seconds of holds $\ge 90^\circ$).
  - **Brush Elevation Control**: Controls vertical brush position based on wrist height.
  - **Creative Templates**: Features outline challenges (Sun, Flower, Butterfly) which require coloring specific zones.
  - **Accuracy & Completion Metrics**: Analyzes canvas coverage and measures stroke accuracy (penalizing out-of-bounds painting).

---

## 4. Belle Pose (`belle_pose.py`) [NEW]
* **Objective**: Replicate elegant classical dance poses to improve joint alignment, motor control, and shoulder stability.
* **Core Features**:
  - **Dance Pose Library**: Includes multiple poses (Belle Pose, First, Second, and Third Position) with specific arm geometry profiles.
  - **Pose Similarity Engine**: Uses joint angle deviations to compute a similarity score out of 100%.
  - **Joint Alignment Helper**: Visualizes arrows and text cues indicating adjustments needed (e.g., "Raise Right Arm", "Straighten Left Elbow").
  - **Stability Evaluation**: Analyzes joint flutter/shakiness over a rolling queue.
  - **Hold Challenge**: Requires maintaining target pose stability and similarity ($\ge 80\%$) continuously for 3 seconds.
