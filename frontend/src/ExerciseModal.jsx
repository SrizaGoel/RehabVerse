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
      "Stand facing the camera with your full upper body clearly visible. Keep your feet shoulder-width apart and maintain an upright posture throughout the exercise.",

      "Each session begins with a silent orchestra. Your objective is to restore the orchestra by completing today's rehabilitation goals.",

      "Slowly raise your surgery arm sideways (shoulder abduction) until you reach today's target Range of Motion (ROM). Hold the position until the timer finishes, then lower your arm in a controlled motion to complete one repetition.",

      "The rehabilitation program consists of six progressive weeks. Each week has a fixed ROM target:\n• Week 1 – 45°\n• Week 2 – 70°\n• Week 3 – 90°\n• Week 4 – 110°\n• Week 5 – 130°\n• Week 6 – 160°.",

      "Unlike the ROM target, the daily Hold Time and Repetition targets are adaptive. Based on your performance from the previous day, the game may increase the challenge, maintain the same difficulty, or reduce the workload to support safe recovery.",

      "Each rehabilitation day consists of two sessions: a Morning Session and an Evening Session. Both sessions must be completed to finish the day's rehabilitation.",

      "As you achieve today's rehabilitation goals, the orchestra is gradually restored:\n• ROM Goal → Unlock the String and Woodwind sections.\n• Hold Time Goal → Unlock the Brass and Percussion sections.\n• Repetition Goal → Unlock the Choir and Piano, completing the full orchestra.",

      "Every seventh day is an Assessment Day. During both the Morning and Evening assessment sessions, you must successfully achieve the week's ROM target together with the required Hold Time and Repetition targets.",

      "If both assessment sessions are completed successfully, you progress to the next rehabilitation week with a higher ROM target. If the assessment is unsuccessful, you remain in the current week and continue rehabilitation until the assessment is passed.",

      "Complete all six rehabilitation weeks to fully restore the Forgotten Orchestra and finish your rehabilitation journey."
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
      "Stand facing the camera with your full upper body clearly visible. Keep your feet shoulder-width apart and maintain an upright posture throughout the exercise.",

      "Your goal is to catch fish by holding your elbow at the target flexion angle. Each successful hold catches one fish, and collecting enough fish completes the rehabilitation session.",

      "Slowly bend your elbow until you reach the target angle shown on the screen. Once you reach the target, keep your arm as steady as possible until the hold timer is completed.",

      "The rehabilitation program consists of four progressive weeks. Each week has a fixed elbow flexion target:\n• Week 1 – 30°\n• Week 2 – 50°\n• Week 3 – 70°\n• Week 4 – 90°.",

      "Within each week, the required Hold Time gradually increases each day to safely improve endurance:\n• Day 1 – 10 seconds\n• Day 2 – 15 seconds\n• Day 3 – 25 seconds\n• Day 4 – 35 seconds\n• Day 5 – 45 seconds\n• Day 6 – 50 seconds\n• Day 7 – 55 seconds.",

      "While holding the target angle, maintain a steady arm position. Higher stability allows the hold timer to progress normally, whereas excessive movement slows down your progress and makes catching the fish more difficult.",

      "Each rehabilitation session requires catching five fish. Every fish represents one successful rehabilitation repetition completed with the required hold duration.",

      "The game automatically adapts to your recovery. If your performance decreases compared to previous sessions, the required Hold Time may be temporarily reduced to make rehabilitation more achievable before gradually increasing again.",

      "After completing Day 7, you automatically progress to the next rehabilitation week with a higher target angle. Continue through all four weeks until the full rehabilitation program is completed."
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
    objective: "Improve hip flexor and quadriceps strength and control through a slow, guided straight-leg raise.",
    primaryMuscle: "Hip Flexors / Quadriceps",
    movement: "Hip Flexion (Straight Leg Raise)",
    target: "Raise your straightened leg to the target height, hold briefly, and lower with control.",
    instructions: [
      "Sit or lie down facing the camera with your full body visible.",
      "Keep your surgery leg straight throughout the movement.",
      "Slowly raise your leg toward the target angle.",
      "Hold the position steadily for a moment at the top.",
      "Lower your leg back down slowly and with control.",
      "Repeat until all repetitions are completed.",
      "You can pause and resume the session at any time."
    ],
    metrics: [
      { name: "Range of Motion", description: "Highest leg-raise angle achieved during the session." },
      { name: "Hold Time", description: "Successful hold duration at the target height." },
      { name: "Repetitions", description: "Total successful repetitions completed." }
    ],
    tips: [
      "Keep your raised leg completely straight throughout.",
      "Move slowly and avoid jerking or swinging the leg.",
      "Keep your lower back flat and relaxed.",
      "Lower your leg with control rather than letting it drop.",
      "Breathe normally during each repetition.",
      "Stop immediately if you experience sharp pain."
    ],
    note: "Progress is based on completing each session's repetition and hold goals rather than calendar days."
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
  tide_caller: {
    title: "Tide Caller",
    objective: "Restore a forgotten coastline by performing controlled bilateral shoulder abduction. Call the tide with both arms, hold at the peak, and release with control to clear each wave.",
    primaryMuscle: "Middle Deltoid (both shoulders)",
    movement: "Bilateral Shoulder Abduction",
    target: "Raise both arms to today's target range of motion, hold steadily, and lower with control to complete each wave.",
    instructions: [
      "Stand facing the camera with your full upper body visible.",
      "Keep your feet shoulder-width apart and maintain an upright posture.",
      "Raise both arms out to the sides together, toward today's target angle.",
      "Hold both arms steady at the peak until the hold timer completes.",
      "Lower both arms back down in a slow, controlled motion.",
      "Repeat until the day's wave target is reached.",
      "Clear the beach and restore the coast by completing every wave."
    ],
    metrics: [
      { name: "Range of Motion", description: "Highest bilateral arm-raise angle achieved during the session." },
      { name: "Symmetry", description: "How evenly both arms move together during each wave." },
      { name: "Hold Time", description: "How steadily the peak position is held for the target duration." },
      { name: "Eccentric Control", description: "Smoothness of the controlled lowering phase - the most clinically important part of each wave." },
      { name: "Waves Cleared", description: "Number of waves completed against today's target." }
    ],
    tips: [
      "Raise both arms together, not one after the other.",
      "Move slowly and avoid using momentum.",
      "Keep your shoulders relaxed - do not shrug.",
      "Lower your arms with control; don't just let them drop.",
      "Breathe normally during each wave.",
      "Ensure your full upper body remains visible to the camera.",
      "Stop immediately if you experience sharp pain."
    ],
    note: "Each day has a fixed target Range of Motion, hold time, and wave count decided in advance - difficulty never adapts mid-session. Missing a day gently rolls back the difficulty rather than penalizing you, and a session can always be ended early."
  },

  aether_guardian: {
    title: "Aether Guardian",
    objective: "Guide two unstable singularities together through controlled bilateral shoulder abduction, merging them with precision and steady control.",
    primaryMuscle: "Middle Deltoid (both shoulders)",
    movement: "Bilateral Shoulder Abduction",
    target: "Reach and hold both arms close together at your target angle to trigger a singularity merger.",
    instructions: [
      "Stand facing the camera with your full upper body visible.",
      "Reach both arms overhead and to the sides, guiding the singularities toward each other.",
      "Hold the position steadily until the merge timer completes.",
      "Lower your arms in a slow, controlled motion after each merger.",
      "Repeat to trigger as many mergers as you can this session.",
      "Precision matters more than speed - a steady, symmetric reach merges faster than a rushed one."
    ],
    metrics: [
      { name: "Mergers", description: "Number of successful singularity mergers completed." },
      { name: "Repetitions", description: "Total arm-raise repetitions performed." },
      { name: "Best Reach Gap", description: "Closest distance achieved between the two singularities (lower is better)." },
      { name: "Best Hold", description: "Longest steady hold at the merge position." },
      { name: "Symmetry", description: "How evenly both arms matched each other during reaches." },
      { name: "Smoothness", description: "How controlled and jerk-free each movement was." }
    ],
    tips: [
      "Keep both arms moving together, not one ahead of the other.",
      "Hold steady once you reach the target - don't drift.",
      "Move smoothly; avoid sudden jerks or momentum.",
      "Keep your shoulders relaxed throughout.",
      "Breathe normally during each hold.",
      "Stop immediately if you experience sharp pain."
    ],
    note: "Difficulty (easy/medium/hard) adjusts how close and how long you must hold to trigger a merger. Session history and streak are saved automatically after each session."
  },

  phoenix_ascend: {
    title: "Phoenix Ascend",
    objective: "Guide a phoenix skyward through controlled shoulder abduction and adduction, holding steady at each altitude to earn combos and level up.",
    primaryMuscle: "Middle Deltoid (both shoulders)",
    movement: "Shoulder Abduction / Adduction",
    target: "Raise your arm to the target altitude, hold it steady, then lower with control to complete each ascent.",
    instructions: [
      "Stand facing the camera with your full upper body visible.",
      "Raise your arm to match the target altitude shown on screen.",
      "Hold steady at the target to charge the ascent.",
      "Lower your arm in a controlled motion to complete the rep.",
      "Chain successful reps together to build your combo.",
      "Advance through levels by completing the reps required for each stage.",
      "Press R at any time to reset your current session."
    ],
    metrics: [
      { name: "Score", description: "Total points earned this session." },
      { name: "Level", description: "Current difficulty stage reached." },
      { name: "Total Repetitions", description: "Number of completed ascents." },
      { name: "Best Combo", description: "Longest streak of consecutive successful reps." },
      { name: "Max Range of Motion", description: "Highest shoulder angle reached during the session." }
    ],
    tips: [
      "Move smoothly toward the target altitude - avoid sudden swings.",
      "Hold steady once you reach the target; small wobbles break your combo.",
      "Keep your shoulders relaxed throughout the movement.",
      "Lower your arm with control rather than letting it drop.",
      "Breathe normally during each hold.",
      "Stop immediately if you experience sharp pain."
    ],
    note: "Session score, level reached, and max range of motion are saved automatically. Levels get progressively more demanding as you advance."
  },
};

const TAB_LABELS = {
  goal: 'Goal',
  instructions: 'Instructions',
  metrics: 'Metrics Tracked',
  tips: 'Success Tips'
};
export default function ExerciseModal({ isOpen, onClose, exercises, challenges, onComplete, onAwardXp, onExerciseComplete, recovery, sessionType, userId, onChallengeComplete, completedExerciseIds }) {

  const [view, setView] = useState('list'); // 'list' | 'detail'
  const [activeItem, setActiveItem] = useState(null);
  const [activeTab, setActiveTab] = useState('goal');
  const [completedIds, setCompletedIds] = useState([]);

  // useEffect(() => {
  //   if (isOpen) {
  //     setView('list');
  //     setActiveItem(null);
  //     setActiveTab('goal');
  //     setCompletedIds([]);
  //   }
  // }, [isOpen]);
  useEffect(() => {
    if (isOpen) {
      setView('list');
      setActiveItem(null);
      setActiveTab('goal');
      setCompletedIds(completedExerciseIds ?? []);
    }
  }, [isOpen, completedExerciseIds]);
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
        onExerciseComplete?.(item.id, gameResult);   // was onExerciseComplete?.()
      }
      if (item.isChallenge && gameResult) {
        onChallengeComplete?.(item.id, gameResult);
      }
      newCompletedIds = [...completedIds, item.id];
      setCompletedIds(newCompletedIds);
    }

    const allDone = exerciseList.length > 0 &&
      exerciseList.every(ex => newCompletedIds.includes(ex.id));

    if (allDone) {
      onComplete?.(gameResult);
    } else {
      setView('list');
    }
  };

  // const finishSession = () => {
  //   onComplete?.();
  // };
  // const launchGame = async (item) => {
  //   // Map frontend side string to game side char
  //   const sideChar = recovery?.side === 'right' ? 'R' : 'L';

  //   const response = await fetch(
  //     "http://127.0.0.1:5000/games/start",
  //     {
  //       method: "POST",
  //       headers: {
  //         "Content-Type": "application/json"
  //       },
  //       body: JSON.stringify({
  //         game: item.id,
  //         user_id: userId ?? null,
  //         recovery_id: recovery?.id ?? null,
  //         side: sideChar,
  //         session_type: sessionType ?? 'morning',
  //         current_week: recovery?.current_week ?? 1
  //       })
  //     }
  //   );

  //   const data = await response.json();

  //   console.log(data);

  //   markComplete(item, data);
  // };
  const launchGame = async (item) => {
    const sideChar = recovery?.side === 'right' ? 'R' : 'L';
    try {
      const response = await fetch("http://127.0.0.1:5000/games/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          game: item.id,
          user_id: userId ?? null,
          recovery_id: recovery?.id ?? null,
          side: sideChar,
          session_type: sessionType ?? 'morning',
          current_week: recovery?.current_week ?? 1
        })
      });

      const data = await response.json();

      if (!response.ok || data?.error) {
        console.error("Game failed to run:", data?.error);
        alert(`Couldn't start this exercise: ${data?.error ?? 'unknown error'}`);
        return; // don't mark complete
      }

      markComplete(item, data);
    } catch (err) {
      console.error("Network/launch error:", err);
      alert("Couldn't reach the game server. Is it running?");
    }
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