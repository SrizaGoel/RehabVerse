import { useEffect, useState } from "react";
import { supabase } from "../lib/supabase";
import { useAuth } from "../context/AuthContext";
import { useNavigate } from "react-router-dom";
import "./PastSessions.css";

const activityNames = {
  forgotten_orchestra: "Forgotten Orchestra",
  fishing: "Fishing Cast",
  leg_raise: "Leg Raise",
  paint_the_object: "Paint the Object",
  belle_pose: "Belle Pose",
  step_stones: "Step Stones",
};
const surgeryNames = {
  rotatorCuffRepair: "Rotator Cuff Repair",
  frozenShoulder: "Frozen Shoulder",
  shoulderArthroscopy: "Shoulder Arthroscopy",
  shoulderReplacement: "Shoulder Replacement",
  labrumRepair: "Labrum Repair",
  tennisElbow: "Tennis Elbow",
  golferElbow: "Golfer's Elbow",
  elbowArthroscopy: "Elbow Arthroscopy",
  distalBicepsRepair: "Distal Biceps Repair",
  tricepsRepair: "Triceps Repair",
  aclReconstruction: "ACL Reconstruction",
  meniscusRepair: "Meniscus Repair",
  kneeReplacement: "Knee Replacement",
  patellarRepair: "Patellar Repair",
};
const metricLabels = {
  rom_goal: "ROM Goal",
  max_angle: "Maximum Angle",
  hold_target: "Hold Target",
  hold_time: "Hold Time",
  rep_target: "Repetition Goal",
  repetitions: "Repetitions",
  orchestra_progress: "Overall Progress",
  stability: "Stability",
  // Paint the Object
  time_taken: "Completion Time (s)",
  accuracy: "Accuracy (%)",
  completion_pct: "Completion %",
  side_hold: "Side Hold (s)",
  // Belle Pose
  avg_similarity: "Avg. Similarity (%)",
  avg_stability: "Avg. Stability (%)",
  overall_score: "Overall Score (%)",
  poses_completed: "Poses Completed",
  total_poses: "Total Poses",
};

const objectiveLabels = {
  rom_met: "ROM",
  hold_met: "Hold",
  reps_met: "Repetitions",
  completed: "Session Completed",
  all_poses_done: "All Poses Done",
  unlocked: "Challenge Unlocked",
};

export default function PastSessions() {

  const navigate = useNavigate();
  const { user } = useAuth();
      async function fetchSessions() {

    setLoading(true);

    const { data, error } = await supabase
      .from("sessions")
      .select("*")
      .eq("user_id", user.id)
      .order("created_at", { ascending: false });

    if (error) {

      console.log(error);

    } else {

      setSessions(data || []);

    }

    setLoading(false);

  }
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {

    if (user) {
      fetchSessions();
    }

  }, [user]);



  function formatDate(date) {

    return new Date(date).toLocaleDateString("en-IN", {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });

  }

function formatMetric(key, value) {

    // Round all decimal numbers to 2 decimal places
    if (typeof value === "number" && !Number.isInteger(value)) {
        value = Number(value.toFixed(2));
    }

    switch (key) {

        case "rom_goal":
        case "max_angle":
            return `${value}°`;

        case "hold_target":
        case "hold_time":
            return `${value} sec`;

        case "orchestra_progress":
            return `${value}%`;

        default:
            return value;

    }

}

  return (<div className="past-page">

    <button
        className="back-btn"
        onClick={() => navigate("/dashboard")}
    >
        ← Dashboard
    </button>

    <div className="history-header">

        <div>

            <h1>Past Sessions</h1>

            <p className="subtitle">
                {sessions.length} completed rehabilitation sessions
            </p>

        </div>

    </div>

    {loading ? (

        <div className="empty-card">

            <h2>Loading...</h2>

        </div>

    ) : sessions.length === 0 ? (

        <div className="empty-card">

            <h2>No Sessions Yet</h2>

            <p>
                Complete your first rehabilitation session to see your history.
            </p>

        </div>

    ) : (

        <div className="history-list">

            {sessions.map((session) => (

<div
                    className={`session-history-card${
                      session.metrics?.missed ? ' missed-card' : session.metrics?.partial ? ' partial-card' : ''
                    }`}
                    key={session.id}
                >

                    <div className="card-header">

                        <div>

<h3>
                                {session.metrics?.missed || session.metrics?.partial
                                    ? surgeryNames[session.activity_id] ?? session.activity_id
                                    : activityNames[session.activity_id] ?? session.activity_id}
                            </h3>

                            <div className="session-tags">

                                {session.metrics?.missed && (
                                  <span className="tag tag-missed">Missed</span>
                                )}

                                <span className="tag">

                                    {
  typeof session.metrics?.session === "string"
    ? session.metrics.session
    : session.metrics?.session?.slot ?? session.metrics?.slot
}

                                </span>

                                <span className="tag">

                                    Week {session.metrics?.session?.week ?? "-"}

                                </span>

                                <span className="tag">

                                    Day {session.metrics?.session?.day ?? "-"}

                                </span>

                            </div>

                        </div>

                        <div className="date">

                            {formatDate(session.created_at)}

                        </div>

                    </div>

{session.metrics?.missed || session.metrics?.partial ? (
                      <div className="section">
                        <h4>{session.metrics.missed ? "Session Missed" : "Partially Completed"}</h4>
                        <div className="objective-list">
                          {(session.metrics.exercises || []).map((exId) => {
                            const done = session.metrics.completed_exercises?.includes(exId);
                            return (
                              <div className="objective-row" key={exId}>
                                <span>{activityNames[exId] ?? exId}</span>
                                <span className={done ? "success" : "failed"}>
                                  {done ? "Completed" : "Missed"}
                                </span>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    ) : (
                      <>
                    <div className="section">

                        <h4>Objectives</h4>

                        <div className="objective-list">

                            {
                                Array.isArray(session.metrics?.objectives) ? (
                                    session.metrics.objectives.map((obj, i) => (
                                        <div className="objective-row" key={i}>
                                            <span>{obj.label}</span>
                                            <span className={obj.completed ? "success" : "failed"}>
                                                {obj.completed ? "Completed" : "Not Met"}
                                            </span>
                                        </div>
                                    ))
                                ) : (
                                    Object.entries(session.metrics?.objectives || {}).map(([key, value]) => (
                                        <div
                                            className="objective-row"
                                            key={key}
                                        >
                                            <span>
                                                {objectiveLabels[key] ?? key}
                                            </span>
                                            <span
                                                className={value ? "success" : "failed"}
                                            >
                                                {value ? "Completed" : "Not Met"}
                                            </span>
                                        </div>
                                    ))
                                )
                            }

                        </div>

                    </div>

                    <div className="section">

                        <h4>Performance Metrics</h4>

                        <div className="metric-grid">

                            {
                                Array.isArray(session.metrics?.metrics) ? (
                                    session.metrics.metrics.map((m, i) => (
                                        <div className="metric-card" key={i}>
                                            <span className="metric-title">{m.label}</span>
                                            <span className="metric-value">
                                                {typeof m.value === "number" && !Number.isInteger(m.value)
                                                    ? Number(m.value.toFixed(2))
                                                    : m.value} {m.unit || ""}
                                            </span>
                                        </div>
                                    ))
                                ) : (
                                    Object.entries(session.metrics?.metrics || {}).map(([key, value]) => (
                                        <div
                                            className="metric-card"
                                            key={key}
                                        >
                                            <span className="metric-title">
                                                {metricLabels[key] ?? key.replaceAll("_", " ")}
                                            </span>
                                            <span className="metric-value">
                                                {formatMetric(key, value)}
                                            </span>
                                        </div>
                                    ))
                                )
                            }

                        </div>

                    </div>
                    </>
                    )}

                </div>

            ))}

        </div>

    )}    </div>

  );

}