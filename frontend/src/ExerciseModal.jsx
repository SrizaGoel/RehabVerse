import { useState, useEffect } from 'react';
import './ExerciseModal.css';

const EXERCISE_DATA = {
  forgotten_orchestra: {
    title: "The Forgotten Orchestra",
    objective: "Restore a forgotten orchestra by performing controlled shoulder abduction exercises. Unlock new instruments by reaching your rehabilitation goals.",
    primaryMuscle: "Middle Deltoid",
    movement: "Shoulder Abduction",
    target: "Reach the required range of motion, hold the position, and complete all repetitions to fully restore today's orchestra.",

    instructions: [
      "Stand facing the camera with your full upper body visible.",
      "Keep your feet shoulder-width apart and maintain an upright posture.",
      "Slowly raise your surgery arm sideways toward the target angle.",
      "Hold the arm steady until the hold timer is completed.",
      "Lower your arm in a controlled motion to finish one repetition.",
      "Repeat until all required repetitions are completed.",
      "Unlock instruments and restore the orchestra by completing every objective."
    ],

    metrics: [
      {
        name: "Range of Motion",
        description: "Highest shoulder abduction angle achieved during the session."
      },
      {
        name: "Hold Time",
        description: "Longest successful hold at the target angle."
      },
      {
        name: "Repetitions",
        description: "Number of correctly completed arm raises."
      },
      {
        name: "Orchestra Progress",
        description: "Percentage of instruments restored in the current session."
      }
    ],

    tips: [
      "Move slowly and avoid using momentum.",
      "Keep your shoulders relaxed—do not shrug.",
      "Maintain an upright posture throughout the movement.",
      "Hold the target position steadily instead of rushing.",
      "Breathe normally during each repetition.",
      "Ensure your full upper body remains visible to the camera.",
      "Stop immediately if you experience sharp pain."
    ],

    note: "Each session starts with a silent orchestra. Completing the Range of Motion, Hold Time, and Repetition goals unlocks instruments until the orchestra is fully restored. Weekly progress is based on rehabilitation milestones, not calendar dates."
  },
  front_arm_raise: {
    title: "Front Arm Raise",
    objective: "Restore shoulder mobility through controlled arm movements while gradually rebuilding strength, endurance, and range of motion.",
    primaryMuscle: "Middle Deltoid (Primary), Supraspinatus (Assists shoulder abduction)",
    movement: "Shoulder Abduction",
    target: "Reach the rehabilitation target Range of Motion (ROM) through smooth, controlled movements.",
    instructions: [
      "Stand upright facing the camera.",
      "Keep your entire upper body visible to the camera.",
      "Slowly raise your surgery arm until you reach the target shoulder angle.",
      "Hold your arm steady at the target angle.",
      "Complete the required range of motion, hold time, and repetitions to finish the current rehabilitation stage.",
      "Once all rehabilitation targets are achieved, you unlock the next stage of your recovery journey."
    ],
    metrics: [
      { name: "Range of Motion", description: "Highest shoulder angle achieved." },
      { name: "Target Angle", description: "Required ROM for current stage." },
      { name: "Hold Time", description: "Successful hold duration." },
      { name: "Repetitions", description: "Total successful repetitions." }
    ],
    tips: [
      "Remain standing throughout the exercise.",
      "Keep your full upper body visible.",
      "Move slowly and avoid momentum.",
      "Do not shrug your shoulders.",
      "Maintain an upright posture.",
      "Breathe normally.",
      "Stop immediately if sharp pain occurs."
    ],
    note: "Progress depends on completing rehabilitation goals rather than calendar weeks."
  },
  fishing: {
    title: "Fishing Cast",
    objective: "Improve elbow flexion through controlled movement, steady holds, and functional reaching while catching fish.",
    primaryMuscle: "Biceps Brachii / Brachialis",
    movement: "Elbow Flexion",
    target: "Reach and maintain the rehabilitation target angle to catch fish.",
    instructions: [
      "Sit or stand facing the camera.",
      "Keep your upper arm close to your body.",
      "Slowly bend your elbow until you reach the target angle.",
      "Hold the position steadily until the fish is caught.",
      "Relax and repeat until all fish are collected."
    ],
    metrics: [
      {
        name: "Range of Motion",
        description: "Maximum elbow flexion angle achieved during the session."
      },
      {
        name: "Target Angle",
        description: "Required elbow flexion angle for the current rehabilitation stage."
      },
      {
        name: "Hold Duration",
        description: "Time the target angle is maintained to successfully catch a fish."
      },
      {
        name: "Stability",
        description: "Measures how steady the arm remains during the hold based on angle variation."
      },
      {
        name: "Fish Collected",
        description: "Number of successful catches completed during the rehabilitation session."
      }
    ],
    tips: [
      "Keep your upper arm close to your torso throughout the movement.",
      "Reach the target angle before beginning the hold.",
      "Maintain a steady position to improve stability.",
      "Avoid sudden or jerky movements.",
      "Stop immediately if you experience sharp pain."
    ],
    note: "Exercise difficulty adapts to the patient's performance. Hold duration may be reduced after weaker sessions and restored as performance improves."
  },
  leg_raise: {
    title: "Leg Raise",
    objective: "Improve knee extension strength and control through a slow, guided leg raise.",
    primaryMuscle: "Quadriceps",
    movement: "Knee Extension",
    target: "Reach the rehabilitation target ROM safely.",
    instructions: [
      "Sit or lie down facing the camera.",
      "Keep your surgery leg extended.",
      "Raise your leg slowly to the target height.",
      "Hold the position until instructed.",
      "Lower the leg slowly.",
      "Repeat until all repetitions are completed."
    ],
    metrics: [
      { name: "Range of Motion", description: "Highest leg raise angle achieved." },
      { name: "Hold Time", description: "Successful hold duration." },
      { name: "Repetitions", description: "Total successful repetitions." }
    ],
    tips: [
      "Keep your surgery leg straight throughout.",
      "Move slowly and avoid jerking motions.",
      "Stop immediately if sharp pain occurs."
    ],
    note: "Progress depends on completing rehabilitation goals rather than calendar weeks."
  },
  paint_the_object: {
    title: "Paint the Object",
    objective: "Improve shoulder abduction and static control by painting objects through steady arm positioning.",
    primaryMuscle: "Middle Deltoid",
    movement: "Shoulder Abduction",
    target: "Raise and hold your arm to paint the entire object accurately.",
    instructions: [
      "Stand facing the camera with your full upper body visible.",
      "Raise your surgery arm to control the paint brush.",
      "Move your wrist to guide the brush over the object.",
      "Hold your arm above the target angle to paint.",
      "Fill at least 85% of the object to complete the challenge."
    ],
    metrics: [
      {
        name: "Completion Percentage",
        description: "Percentage of the object successfully painted."
      },
      {
        name: "Painting Accuracy",
        description: "Measures how accurately painting stays within the object boundaries."
      },
      {
        name: "Completion Time",
        description: "Time taken to finish the painting after the challenge unlocks."
      },
      {
        name: "Side Hold Progress",
        description: "Cumulative shoulder hold time used to unlock the painting challenge."
      }
    ],
    tips: [
      "Keep your movements smooth and controlled.",
      "Maintain your arm above the target angle while painting.",
      "Avoid painting outside the object boundaries.",
      "Keep your entire upper body visible to the camera.",
      "Stop immediately if you experience sharp pain."
    ],
    note: "This optional challenge unlocks after accumulating 60 seconds of successful side-arm holds. Your best completion time is saved for each painting template."
  },
  belle_pose: {
    title: "Belle Pose",
    objective: "Improve shoulder mobility, posture, and upper-limb control by matching and holding a series of ballet-inspired poses.",
    primaryMuscle: "Middle Deltoid / Rotator Cuff",
    movement: "Shoulder Abduction & Multi-Joint Static Hold",
    target: "Match each target pose accurately and maintain it steadily for the required duration.",
    instructions: [
      "Stand facing the camera with your full upper body visible.",
      "Copy the highlighted target pose.",
      "Adjust your shoulder and elbow positions until they match the guide.",
      "Hold the pose steadily for 3 seconds.",
      "Complete all four poses to finish the challenge."
    ],
    metrics: [
      {
        name: "Pose Similarity",
        description: "Measures how closely your shoulder and elbow angles match the target pose."
      },
      {
        name: "Pose Stability",
        description: "Evaluates how steadily the pose is maintained during the hold."
      },
      {
        name: "Hold Duration",
        description: "Time the pose is continuously maintained before completion."
      },
      {
        name: "Poses Completed",
        description: "Number of ballet poses successfully completed during the session."
      },
      {
        name: "Overall Score",
        description: "Combined performance score based on average pose similarity and stability."
      }
    ],
    tips: [
      "Keep your shoulders relaxed throughout the movement.",
      "Match the target pose before beginning the hold.",
      "Avoid unnecessary body movement while holding the pose.",
      "Breathe normally and maintain good posture.",
      "Stop immediately if you experience sharp pain."
    ],
    note: "Complete all four ballet-inspired poses successfully to finish the optional challenge. Individual pose scores and overall performance are recorded for progress tracking."
  },
};

const TAB_LABELS = {
  goal: 'Goal',
  instructions: 'Instructions',
  metrics: 'Metrics Tracked',
  tips: 'Success Tips'
};

export default function ExerciseModal({ isOpen, onClose, exercises, challenges, onComplete, onAwardXp, onExerciseComplete, recovery, sessionType, userId, onChallengeComplete }) {
  const [view, setView] = useState('list'); // 'list' | 'detail'
  const [activeItem, setActiveItem] = useState(null);
  const [activeTab, setActiveTab] = useState('goal');
  const [completedIds, setCompletedIds] = useState([]);

  useEffect(() => {
    if (isOpen) {
      setView('list');
      setActiveItem(null);
      setActiveTab('goal');
      setCompletedIds([]);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const exerciseList = (exercises || []).map(id => ({ id, ...EXERCISE_DATA[id] }));
  const challengeList = (challenges || []).map(id => ({ id, ...EXERCISE_DATA[id] }));

  const allExercisesDone = exerciseList.length > 0 && exerciseList.every(ex => completedIds.includes(ex.id));
  const completedExerciseCount = exerciseList.filter(ex => completedIds.includes(ex.id)).length;

  const openDetail = (item) => {
    setActiveItem(item);
    setActiveTab('goal');
    setView('detail');
  };

  const backToList = () => setView('list');

  const markComplete = (item, gameResult) => {
    let newCompletedIds = completedIds;

    if (!completedIds.includes(item.id)) {
      onAwardXp?.(item.isChallenge ? 25 : 10);
      if (!item.isChallenge) {
        onExerciseComplete?.();
      }
      // If it's a challenge, persist its specific metrics immediately
      if (item.isChallenge && gameResult) {
        onChallengeComplete?.(item.id, gameResult);
      }
      newCompletedIds = [...completedIds, item.id];
      setCompletedIds(newCompletedIds);
    }

    // Auto-complete session the moment all exercises are done
    const allDone = exerciseList.length > 0 &&
      exerciseList.every(ex => newCompletedIds.includes(ex.id));

    if (allDone) {
      onComplete?.(gameResult); // triggers handleSessionComplete → closes modal + saves to DB
    } else {
      setView('list');
    }
  };

  const finishSession = () => {
    onComplete?.();
  };
  const launchGame = async (item) => {
    // Map frontend side string to game side char
    const sideChar = recovery?.side === 'right' ? 'R' : 'L';

    const response = await fetch(
      "http://127.0.0.1:5000/games/start",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          game: item.id,
          user_id: userId ?? null,
          recovery_id: recovery?.id ?? null,
          side: sideChar,
          session_type: sessionType ?? 'morning',
          current_week: recovery?.current_week ?? 1
        })
      }
    );

    const data = await response.json();

    console.log(data);

    markComplete(item, data);
  };
  const renderItemCard = (item, index, isChallenge) => {
    const isDone = completedIds.includes(item.id);
    return (
      <div
        className={`exercise-card${isChallenge ? ' challenge-card' : ''}${isDone ? ' is-complete' : ''}`}
        key={item.id}
        onClick={() => openDetail({ ...item, isChallenge })}
      >
        <div className="exercise-number">{isDone ? <i className="fa-solid fa-check"></i> : index + 1}</div>
        <div className="exercise-details">
          <h3>{item.title}</h3>
          <p>{item.objective}</p>
        </div>
        <div className="exercise-status">
          <i className="fa-solid fa-chevron-right"></i>
        </div>
      </div>
    );
  };

  return (
    <div className="popup" style={{ display: 'flex' }}>
      <div className="popup-box">
        <span className="close" onClick={onClose}>
          &times;
        </span>

        {view === 'list' && (
          <div className="session-window">
            <div className="session-window-header">
              <h1>Today's Rehabilitation Session</h1>
              <p>Tap an exercise or challenge below to open it.</p>
            </div>

            <div className="session-section">
              <h2>Exercises</h2>
              <div className="exercise-list">
                {exerciseList.map((ex, i) => renderItemCard(ex, i, false))}
              </div>
            </div>

            {challengeList.length > 0 && (
              <div className="session-section">
                <h2>Optional Challenges</h2>
                <div className="exercise-list">
                  {challengeList.map((ch, i) => renderItemCard(ch, i, true))}
                </div>
              </div>
            )}

            {/* Progress status — auto-completes when all done, no button needed */}
            {!allExercisesDone && (
              <div className="session-progress-status">
                <i className="fa-solid fa-circle-info"></i>
                Complete all exercises to finish &nbsp;
                <strong>({completedExerciseCount}/{exerciseList.length})</strong>
              </div>
            )}
          </div>
        )}

        {view === 'detail' && activeItem && (
          <div className="exercise-window">
            <aside className="sidebar">
              <button className="back-link" onClick={backToList}>
                <i className="fa-solid fa-arrow-left"></i> Back to Sessions
              </button>
              <div className="exercise-title">{activeItem.title}</div>

              {Object.keys(TAB_LABELS).map(tabId => (
                <button
                  key={tabId}
                  className={`tab ${activeTab === tabId ? 'active' : ''}`}
                  onClick={() => setActiveTab(tabId)}
                >
                  {TAB_LABELS[tabId]}
                </button>
              ))}

              <button
                className={`start-tab ${activeTab === 'start' ? 'active' : ''}`}
                onClick={() => setActiveTab('start')}
              >
                Start Session
              </button>
            </aside>

            <main className="content">
              {activeTab === 'goal' && (
                <section className="tab-content active">
                  <h2>Exercise Goal</h2>
                  <div className="goal-layout">
                    <div className="goal-info goal-info-full">
                      <h3>Objective</h3>
                      <p>{activeItem.objective}</p>
                      <div className="info-card">
                        <strong>Primary Muscle</strong>
                        <p>{activeItem.primaryMuscle}</p>
                      </div>
                      <div className="info-card">
                        <strong>Movement</strong>
                        <p>{activeItem.movement}</p>
                      </div>
                      <div className="info-card">
                        <strong>Target</strong>
                        <p>{activeItem.target}</p>
                      </div>
                    </div>
                  </div>
                </section>
              )}

              {activeTab === 'instructions' && (
                <section className="tab-content active">
                  <h2>Instructions</h2>
                  <ol>
                    {activeItem.instructions.map((step, i) => (
                      <li key={i}>{step}</li>
                    ))}
                  </ol>
                  <div className="note">{activeItem.note}</div>
                </section>
              )}

              {activeTab === 'metrics' && (
                <section className="tab-content active">
                  <h2>Metrics Tracked</h2>
                  <table>
                    <tbody>
                      <tr>
                        <th>Metric</th>
                        <th>Description</th>
                      </tr>
                      {activeItem.metrics.map((m, i) => (
                        <tr key={i}>
                          <td>{m.name}</td>
                          <td>{m.description}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </section>
              )}

              {activeTab === 'tips' && (
                <section className="tab-content active">
                  <h2>Success Tips</h2>
                  <ul>
                    {activeItem.tips.map((tip, i) => (
                      <li key={i}>{tip}</li>
                    ))}
                  </ul>
                </section>
              )}

              {activeTab === 'start' && (
                <section className="tab-content active">
                  <div className="start-screen">
                    <h2>Ready?</h2>
                    <p>
                      Ensure your camera is positioned correctly and there is enough room
                      to perform the movement safely.
                    </p>
                    <button className="start-button" onClick={() => launchGame(activeItem)}>
                      Start Session
                    </button>
                  </div>
                </section>
              )}
            </main>
          </div>
        )}
      </div>
    </div>
  );
}