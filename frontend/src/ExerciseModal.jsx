import { useState, useEffect } from 'react';
import './ExerciseModal.css';

const EXERCISE_DATA = {
  forgotten_orchestra: {
    title: "Side Arm Raise",
    objective: "Improve shoulder abduction through controlled movement while maintaining correct posture throughout the exercise.",
    primaryMuscle: "Middle Deltoid",
    movement: "Shoulder Abduction",
    target: "Reach the rehabilitation target ROM safely.",
    instructions: [
      "Stand upright facing the camera.",
      "Keep your feet shoulder-width apart.",
      "Raise your surgery arm sideways.",
      "Reach the highlighted target angle.",
      "Hold the position until instructed.",
      "Lower the arm slowly.",
      "Repeat until all repetitions are completed."
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
    objective: "Improve elbow flexion and extension through a controlled, functional casting motion.",
    primaryMuscle: "Biceps Brachii / Triceps Brachii",
    movement: "Elbow Flexion & Extension",
    target: "Reach the rehabilitation target ROM safely.",
    instructions: [
      "Sit or stand facing the camera.",
      "Keep your upper arm close to your body.",
      "Bend your elbow slowly toward the target angle.",
      "Extend your elbow back out with control.",
      "Repeat until all repetitions are completed."
    ],
    metrics: [
      { name: "Range of Motion", description: "Highest elbow flexion angle achieved." },
      { name: "Target Angle", description: "Required ROM for current stage." },
      { name: "Repetitions", description: "Total successful repetitions." }
    ],
    tips: [
      "Keep your upper arm still and close to your torso.",
      "Move slowly and avoid swinging.",
      "Stop immediately if sharp pain occurs."
    ],
    note: "Progress depends on completing rehabilitation goals rather than calendar weeks."
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
    objective: "A fun optional challenge that encourages fluid, controlled shoulder movement by tracing shapes in the air.",
    primaryMuscle: "Middle Deltoid",
    movement: "Shoulder Circumduction",
    target: "Trace the highlighted shape smoothly and accurately.",
    instructions: [
      "Stand upright facing the camera.",
      "Keep your surgery arm visible at all times.",
      "Trace the outline of the shown object with your arm.",
      "Move smoothly, avoiding sudden jerks.",
      "Complete the shape to finish the challenge."
    ],
    metrics: [
      { name: "Path Accuracy", description: "How closely you traced the shape." },
      { name: "Completion Time", description: "Time taken to complete the trace." }
    ],
    tips: [
      "Move slowly and stay relaxed.",
      "Keep your full upper body visible.",
      "Stop immediately if sharp pain occurs."
    ],
    note: "Optional challenge — completing it is not required to finish today's session."
  },
  belle_pose: {
    title: "Belle Pose",
    objective: "An optional challenge that rewards holding a stable, controlled shoulder position.",
    primaryMuscle: "Middle Deltoid / Rotator Cuff",
    movement: "Shoulder Abduction Hold",
    target: "Hold the pose steady for the required duration.",
    instructions: [
      "Stand upright facing the camera.",
      "Raise your surgery arm to the highlighted pose.",
      "Hold the position as steady as possible.",
      "Maintain the hold for the required duration."
    ],
    metrics: [
      { name: "Hold Stability", description: "How steady the pose was maintained." },
      { name: "Hold Time", description: "Successful hold duration." }
    ],
    tips: [
      "Engage your core for extra stability.",
      "Breathe normally throughout the hold.",
      "Stop immediately if sharp pain occurs."
    ],
    note: "Optional challenge — completing it is not required to finish today's session."
  },
  step_stones: {
    title: "Step Stones",
    objective: "An optional challenge that builds knee control and balance through guided stepping.",
    primaryMuscle: "Quadriceps / Hamstrings",
    movement: "Knee Flexion & Extension",
    target: "Step onto each highlighted stone with control.",
    instructions: [
      "Stand facing the camera with enough space to step.",
      "Step onto each highlighted stone in sequence.",
      "Keep your movements slow and controlled.",
      "Complete the full sequence to finish the challenge."
    ],
    metrics: [
      { name: "Step Accuracy", description: "How accurately each stone was reached." },
      { name: "Completion Time", description: "Time taken to complete the sequence." }
    ],
    tips: [
      "Hold onto a stable surface if needed for balance.",
      "Move slowly and avoid rushing.",
      "Stop immediately if sharp pain occurs."
    ],
    note: "Optional challenge — completing it is not required to finish today's session."
  }
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