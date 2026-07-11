import { useState, useEffect } from 'react';
import './Dashboard.css';
import Body from './Body';
import ExerciseModal from './ExerciseModal';
import league1 from './assets/league1.png';
import league2 from './assets/league2.png';
import league3 from './assets/league3.png';
import league4 from './assets/league4.png';
import league5 from './assets/league5.png';
import league6 from './assets/league6.png';
import league7 from './assets/league7.png';
import league8 from './assets/league8.png';
import league9 from './assets/league9.png';
import league10 from './assets/league10.png';
import { useAuth } from "./context/AuthContext";
import { supabase } from "./lib/supabase";
import ProfileSetup from "./pages/ProfileSetup";
import { useNavigate } from "react-router-dom";

const leagueImages = {
  1: league1,
  2: league2,
  3: league3,
  4: league4,
  5: league5,
  6: league6,
  7: league7,
  8: league8,
  9: league9,
  10: league10
};

const rehabPrograms = {
  rotatorCuffRepair: {
    affectedPart: "shoulder",
    exercises: [
      "forgotten_orchestra"
    ],
    challenges: [
      "paint_the_object",
      "belle_pose"
    ]
  },
  frozenShoulder: {
    affectedPart: "shoulder",
    exercises: [
      "forgotten_orchestra"
    ],
    challenges: [
      "paint_the_object",
      "belle_pose"
    ]
  },
  shoulderArthroscopy: {
    affectedPart: "shoulder",
    exercises: [
      "forgotten_orchestra"
    ],
    challenges: [
      "paint_the_object",
      "belle_pose"
    ]
  },
  shoulderReplacement: {
    affectedPart: "shoulder",
    exercises: [
      "forgotten_orchestra"
    ],
    challenges: [
      "paint_the_object",
      "belle_pose"
    ]
  },
  labrumRepair: {
    affectedPart: "shoulder",
    exercises: [
      "forgotten_orchestra"
    ],
    challenges: [
      "paint_the_object",
      "belle_pose"
    ]
  },
  tennisElbow: {
    affectedPart: "elbow",
    exercises: [
      "fishing"
    ],

    challenges: []
  },
  golferElbow: {
    affectedPart: "elbow",
    exercises: [
      "fishing"
    ],

    challenges: []
  },

  elbowArthroscopy: {
    affectedPart: "elbow",

    exercises: [
      "fishing"
    ],

    challenges: []
  },

  distalBicepsRepair: {
    affectedPart: "elbow",

    exercises: [
      "fishing"
    ],

    challenges: []
  },

  tricepsRepair: {
    affectedPart: "elbow",
    exercises: [
      "fishing"
    ],

    challenges: []
  },

  aclReconstruction: {
    affectedPart: "knee",

    exercises: [
      "leg_raise"
    ],

    challenges: [
      "step_stones"
    ]
  },

  meniscusRepair: {
    affectedPart: "knee",

    exercises: [
      "leg_raise"
    ],

    challenges: [
      "step_stones"
    ]
  },

  kneeReplacement: {
    affectedPart: "knee",

    exercises: [
      "leg_raise"
    ],

    challenges: [
      "step_stones"
    ]
  },

  patellarRepair: {
    affectedPart: "knee",

    exercises: [
      "leg_raise"
    ],

    challenges: [
      "step_stones"
    ]
  }
};

// if that particular exercise in games section have certain week numners for example some exercise have only  7 weeks then last week set at recovery automatically

const getSurgeryDisplayName = (key) => {
  const names = {
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
    patellarRepair: "Patellar Repair"
  };
  return names[key] || key;
};

export function Dashboard() {
  const [activeRecoveries, setActiveRecoveries] = useState([]);

  const [selectedSurgery, setSelectedSurgery] = useState('rotatorCuffRepair');
  const [selectedSide, setSelectedSide] = useState('left');
  const [selectedWeek, setSelectedWeek] = useState(1);


  const [modalOpen, setModalOpen] = useState(false);
  const [currentExercises, setCurrentExercises] = useState([]);
  const [currentChallenges, setCurrentChallenges] = useState([]);
  const [activeExerciseSession, setActiveExerciseSession] = useState(null); // { recoveryId, sessionType }

  const [activeSection, setActiveSection] = useState('surgery-part');

  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const handleScroll = () => {
      const surgeryPart = document.getElementById("surgery-part");
      const progressPart = document.getElementById("progress-part");
      if (!surgeryPart || !progressPart) return;

      const scrollY = window.scrollY;
      const surgeryTop = surgeryPart.offsetTop - 150;
      const progressTop = progressPart.offsetTop - 150;

      if (scrollY >= progressTop) {
        setActiveSection('progress-part');
      } else {
        setActiveSection('surgery-part');
      }
    };

    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const formatCooldownTime = (ms) => {
    const totalSeconds = Math.max(0, Math.floor(ms / 1000));
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;

    if (hours > 0) {
      return `${hours}h ${minutes}m ${seconds}s`;
    }
    if (minutes > 0) {
      return `${minutes}m ${seconds}s`;
    }
    return `${seconds}s`;
  };

  const getLeague = (xpValue) => {
    if (xpValue >= 0 && xpValue <= 200) return 1;
    if (xpValue <= 745) return 2;
    if (xpValue <= 1499) return 3;
    if (xpValue <= 2499) return 4;
    if (xpValue <= 3999) return 5;
    if (xpValue <= 5999) return 6;
    if (xpValue <= 7999) return 7;
    if (xpValue <= 9999) return 8;
    if (xpValue <= 14999) return 9;
    return 10;
  };

  async function handleAddRecovery() {

    const exists = activeRecoveries.some(
      rec =>
        rec.surgery === selectedSurgery &&
        rec.side === selectedSide
    );

    if (exists) {
      alert("This recovery already exists!");
      return;
    }

    // Only count exercises (games), not optional challenges
    const exerciseCount = rehabPrograms[selectedSurgery].exercises.length;

    const { error } = await supabase
      .from("user_recoveries")
      .insert({
        user_id: user.id,
        surgery: selectedSurgery,
        side: selectedSide,
        current_week: selectedWeek,

        morning_progress: 0,
        morning_total: exerciseCount,
        morning_completed: false,

        evening_progress: 0,
        evening_total: exerciseCount,
        evening_completed: false
      });

    if (error) {
      console.error(error);
      alert(error.message);
      return;
    }

    fetchRecoveries();
  }

  async function handleRemoveRecovery(id) {

    const { error } = await supabase
      .from("user_recoveries")
      .delete()
      .eq("id", id);

    if (error) {
      console.error(error);
      return;
    }

    fetchRecoveries();
  }

  const openExercise = (recoveryId, sessionType, surgeryKey) => {
    const program = rehabPrograms[surgeryKey];
    setCurrentExercises(program.exercises);
    setCurrentChallenges(program.challenges);
    setActiveExerciseSession({ recoveryId, sessionType });
    setModalOpen(true);
  };

  const handleSessionComplete = async (gameResult) => {
    console.log("Session completed!");
    console.log(activeExerciseSession);
    if (!activeExerciseSession) return;

    const { recoveryId, sessionType } = activeExerciseSession;

    // If recoveryId is null (e.g. Quick Start button), just close modal
    if (!recoveryId) {
      setModalOpen(false);
      setActiveExerciseSession(null);
      return;
    }

    let updates = {};

    // Use actual exercises count (games only, not challenges)
    const exerciseCount = rehabPrograms[
      activeRecoveries.find(r => r.id === recoveryId)?.surgery
    ]?.exercises?.length ?? 1;

    if (sessionType === "morning") {
      updates = {
        morning_progress: exerciseCount,
        morning_completed: true,
        morning_completed_at: new Date().toISOString()
      };
    } else {
      updates = {
        evening_progress: exerciseCount,
        evening_completed: true
      };
    }

    const { data, error } = await supabase
      .from("user_recoveries")
      .update(updates)
      .eq("id", recoveryId)
      .select();

    console.log("Recovery ID:", recoveryId);
    console.log("Returned Data:", data);
    console.log("Error:", error);

    if (error) {
      console.error(error);
      setModalOpen(false);
      setActiveExerciseSession(null);
      return;
    }

    const recovery = activeRecoveries.find(r => r.id === recoveryId);

    if (recovery) {
      const activityId =
        sessionType === "morning"
          ? rehabPrograms[recovery.surgery].exercises[0]
          : rehabPrograms[recovery.surgery].challenges?.[0] ?? rehabPrograms[recovery.surgery].exercises[0];

      await supabase
        .from("sessions")
        .insert({
          user_id: user.id,
          activity_id: activityId,
          completed: true,
          metrics: gameResult
        });

      // Advance week in DB if the game returned a higher week number
      const gameWeek = gameResult?.session?.week;
      if (gameWeek && gameWeek > recovery.current_week) {
        await supabase
          .from('user_recoveries')
          .update({ current_week: gameWeek })
          .eq('id', recoveryId);
      }

      // Increment streak when evening session completes
      if (sessionType === 'evening') {
        const { data: freshProgress } = await supabase
          .from('user_progress')
          .select('current_streak')
          .eq('user_id', user.id)
          .single();
        await supabase
          .from('user_progress')
          .update({ current_streak: (freshProgress?.current_streak ?? 0) + 1 })
          .eq('user_id', user.id);
      }
    }

    // Refresh both recoveries and user data (XP, streak, etc.)
    await Promise.all([fetchRecoveries(), fetchUserData()]);
    setModalOpen(false);
    setActiveExerciseSession(null);
  };
  async function handleAwardXp(amount) {
    // Fetch current XP fresh from DB to avoid stale closure issues
    const { data: freshProgress, error: fetchError } = await supabase
      .from("user_progress")
      .select("xp")
      .eq("user_id", user.id)
      .single();

    if (fetchError) {
      console.log(fetchError);
      return;
    }

    const newXp = (freshProgress?.xp ?? 0) + amount;

    const { error } = await supabase
      .from("user_progress")
      .update({ xp: newXp })
      .eq("user_id", user.id);

    if (error) {
      console.log(error);
      return;
    }

    fetchUserData();
  }

  async function handleChallengeComplete(challengeId, gameResult) {
    if (!activeExerciseSession?.recoveryId) return;
    const { recoveryId } = activeExerciseSession;

    await supabase
      .from('sessions')
      .insert({
        user_id: user.id,
        activity_id: challengeId,
        completed: true,
        metrics: gameResult
      });
  }

  // Optimistically update local progress count when a single exercise is completed
  // so the card shows 0/1 → 1/1 immediately without waiting for DB
  function handleExerciseComplete() {
    if (!activeExerciseSession?.recoveryId) return;
    const { recoveryId, sessionType } = activeExerciseSession;
    setActiveRecoveries(prev => prev.map(rec => {
      if (rec.id !== recoveryId) return rec;
      if (sessionType === 'morning') {
        return { ...rec, morning_progress: Math.min(rec.morning_progress + 1, rec.morning_total) };
      } else {
        return { ...rec, evening_progress: Math.min(rec.evening_progress + 1, rec.evening_total) };
      }
    }));
  }

  // Cooldown & Status Computations for morning session
  const getMorningDetails = (rec) => {
    if (rec.morning_completed) {
      return {
        badgeText: "Completed",
        badgeClass: "badge completed",
        btnText: "Completed",
        cardClass: "session-card morning-completed",
        disabled: true
      };
    }
    return {
      badgeText: "Available",
      badgeClass: "badge available",
      btnText: "Continue Session",
      cardClass: "session-card",
      disabled: false
    };
  };

  const getEveningDetails = (rec) => {
    if (rec.evening_completed) {
      return {
        badgeText: "Completed",
        badgeClass: "badge completed",
        btnText: "Completed",
        cardClass: "session-card evening-completed",
        disabled: true
      };
    }

    if (!rec.morning_completed) {
      return {
        badgeText: "Locked",
        badgeClass: "badge locked",
        btnText: "Locked",
        cardClass: "session-card locked-card",
        disabled: true,
        reason: "Waiting for morning session"
      };
    }

    const elapsed = currentTime.getTime() - new Date(rec.morning_completed_at).getTime();
    const cooldown = 2 * 60 * 60 * 1000;
    if (elapsed < cooldown) {
      const remainingMs = cooldown - elapsed;
      return {
        badgeText: formatCooldownTime(remainingMs),
        badgeClass: "badge locked",
        btnText: "Locked",
        cardClass: "session-card locked-card",
        disabled: true,
        reason: `Available in ${formatCooldownTime(remainingMs)}`
      };
    }

    return {
      badgeText: "Available",
      badgeClass: "badge available",
      btnText: "Continue Session",
      cardClass: "session-card",
      disabled: false
    };
  };

  const totalExercises = activeRecoveries.reduce((sum, rec) => sum + rec.morning_total + rec.evening_total, 0);
  const completedExercises = activeRecoveries.reduce((sum, rec) => sum + rec.morning_progress + rec.evening_progress, 0);
  const progressPercent = totalExercises > 0 ? Math.round((completedExercises / totalExercises) * 100) : 0;

  const recoveryStatusText = activeRecoveries
    .map(r => `${getSurgeryDisplayName(r.surgery)} (${r.side === 'left' ? 'L' : 'R'})`)
    .join(', ') || 'No active recoveries';

  const { user } = useAuth();
  const [profile, setProfile] = useState(null);
  const [showProfileSetup, setShowProfileSetup] = useState(false);
  const [progress, setProgress] = useState(null);
  async function fetchProfile() {
    if (!user) return;

    const { data, error } = await supabase
      .from("profiles")
      .select("*")
      .eq("id", user.id)
      .maybeSingle();

    console.log(data);
    console.log(error);

    if (error) {
      console.log(error);
      return;
    }

    setProfile(data);

    if (!data || !data.full_name) {
      setShowProfileSetup(true);
    }
  }
  async function fetchUserData() {

    // Profile
    const { data: profileData, error: profileError } = await supabase
      .from("profiles")
      .select("*")
      .eq("id", user.id)
      .single();

    if (!profileError)
      setProfile(profileData);

    // Progress
    const { data: progressData, error: progressError } = await supabase
      .from("user_progress")
      .select("*")
      .eq("user_id", user.id)
      .single();

    if (!progressError)
      setProgress(progressData);

  }
  async function fetchRecoveries() {

    const { data, error } = await supabase
      .from("user_recoveries")
      .select("*")
      .eq("user_id", user.id)
      .order("created_at", { ascending: true });

    if (error) {
      console.error(error);
      return;
    }

    // ── Daily reset: if a recovery's last activity was before today, reset its
    //    session flags, record any missed sessions, and reset the streak.
    const todayStr = new Date().toLocaleDateString('sv-SE');   // YYYY-MM-DD in local time
    const updatedRecoveries = [];

    for (const rec of (data || [])) {
      // Determine the date of last interaction
      const lastDate = rec.morning_completed_at
        ? new Date(rec.morning_completed_at).toLocaleDateString('sv-SE')
        : null;

      const needsReset = lastDate && lastDate < todayStr;

      if (needsReset) {
        // Count elapsed days so we can record a missed-session entry for each
        const lastD = new Date(lastDate);
        const todayD = new Date(todayStr);
        const elapsedDays = Math.max(
          1,
          Math.round((todayD - lastD) / (1000 * 60 * 60 * 24))
        );

        // For every elapsed day, log missed sessions that were not completed
        const missedInserts = [];
        for (let d = 0; d < elapsedDays; d++) {
          const missedDate = new Date(lastD);
          missedDate.setDate(lastD.getDate() + d);
          const missedDateStr = missedDate.toISOString();

          if (d === 0) {
            // The last-active day itself — only log what was NOT completed
            if (!rec.morning_completed) {
              missedInserts.push({
                user_id: user.id,
                activity_id: (rehabPrograms[rec.surgery]?.exercises?.[0]) ?? 'forgotten_orchestra',
                completed: false,
                metrics: { missed: true, slot: 'morning', date: missedDateStr, recovery_id: rec.id }
              });
            }
            if (!rec.evening_completed) {
              missedInserts.push({
                user_id: user.id,
                activity_id: (rehabPrograms[rec.surgery]?.exercises?.[0]) ?? 'forgotten_orchestra',
                completed: false,
                metrics: { missed: true, slot: 'evening', date: missedDateStr, recovery_id: rec.id }
              });
            }
          } else {
            // Fully missed days — both slots
            for (const slot of ['morning', 'evening']) {
              missedInserts.push({
                user_id: user.id,
                activity_id: (rehabPrograms[rec.surgery]?.exercises?.[0]) ?? 'forgotten_orchestra',
                completed: false,
                metrics: { missed: true, slot, date: missedDateStr, recovery_id: rec.id }
              });
            }
          }
        }

        if (missedInserts.length > 0) {
          await supabase.from('sessions').insert(missedInserts);
        }

        // Reset streak if any session was missed
        if (!rec.morning_completed || !rec.evening_completed) {
          await supabase
            .from('user_progress')
            .update({ current_streak: 0 })
            .eq('user_id', user.id);
        }

        // Reset the recovery for today
        const { data: resetData } = await supabase
          .from('user_recoveries')
          .update({
            morning_progress: 0,
            morning_completed: false,
            morning_completed_at: null,
            evening_progress: 0,
            evening_completed: false
          })
          .eq('id', rec.id)
          .select()
          .single();

        updatedRecoveries.push(resetData ?? { ...rec, morning_progress: 0, morning_completed: false, morning_completed_at: null, evening_progress: 0, evening_completed: false });
      } else {
        updatedRecoveries.push(rec);
      }
    }

    setActiveRecoveries(updatedRecoveries);
  }
  useEffect(() => {
    fetchProfile();
  }, []);
  useEffect(() => {

    if (!user) return;

    fetchUserData();
    fetchRecoveries();

  }, [user]);

  const currentXp = progress?.xp ?? 0;
  const currentWeek = progress?.current_week ?? 1;
  const currentDay = progress?.current_day ?? 1;
  const currentStreak = progress?.current_streak ?? 0;
  const morningCompleted = progress?.morning_completed ?? false;
  const eveningCompleted = progress?.evening_completed ?? false;
  const navigate = useNavigate();
  const [showProfile, setShowProfile] = useState(false);
async function handleLogout() {

    const { error } = await supabase.auth.signOut();

    if(error){
        console.log(error);
    }

    setShowProfile(false);

}
useEffect(() => {

    function closeProfile(e){

        if(!e.target.closest(".profile-container")){

            setShowProfile(false);

        }

    }

    document.addEventListener("click",closeProfile);

    return ()=>document.removeEventListener("click",closeProfile);

},[]);
  return (
    <>
      {showProfileSetup && (

        <ProfileSetup

          onComplete={() => {
            setShowProfileSetup(false);
            fetchProfile();
          }}

        />

      )}
      <nav className="navbar">
        <div className="logo">RehabVerse</div>
        <ul className="nav-links">
          <li>
            <a href="#surgery-part" className={activeSection === 'surgery-part' ? 'active' : ''}>
              Surgery
            </a>
          </li>
          <li>
            <a href="#progress-part" className={activeSection === 'progress-part' ? 'active' : ''}>
              My Progress
            </a>
          </li>
        </ul>
        <div className="profile-container">

<div
    className="profile-circle"
    onClick={(e)=>{

        e.stopPropagation();

        setShowProfile(prev=>!prev);

    }}
>
            {profile?.full_name
              ?.split(" ")
              .map(n => n[0])
              .join("")
              .slice(0, 2)
              .toUpperCase()}
          </div>

          {showProfile && (

            <div className="profile-dropdown">

              <div className="profile-top">

                <div className="avatar">

                  {profile?.full_name
                    ?.split(" ")
                    .map(n => n[0])
                    .join("")
                    .slice(0, 2)
                    .toUpperCase()}

                </div>

                <div>

                  <h3>{profile?.full_name}</h3>

                  <p>{user?.email}</p>

                </div>

              </div>

              <div className="profile-divider"></div>

              <div className="profile-row">
                <span>Age</span>
                <span>{profile?.age}</span>
              </div>

              <div className="profile-row">
                <span>Gender</span>
                <span>{profile?.gender}</span>
              </div>

              <div className="profile-divider"></div>

              <button
                className="logout-btn"
                onClick={handleLogout}
              >
                Logout
              </button>

            </div>

          )}

        </div>
      </nav>

      <main className="dashboard">
        <section className="hero-card" id="surgery-part">
          <div className="recovery-header">
            <div className="status-left">
              <span className="live-dot"></span>
              <div>
                <h3>Recovery Status</h3>
                <p>{recoveryStatusText}</p>
              </div>
            </div>
            <span className="status-pill">On Track</span>
          </div>

          <div className="section-divider"></div>

          <div className="today-header">
            <h2>Today's Sessions</h2>
            <p>Time between Morning and Evening sessions must be at least 2 hours.</p>
          </div>

          {activeRecoveries.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text-light)' }}>
              <p>No active recoveries. Add a recovery path below to start your sessions!</p>
            </div>
          ) : (
            activeRecoveries.map((rec) => {
              const morningDetails = getMorningDetails(rec);
              const eveningDetails = getEveningDetails(rec);
              const morningWidth = `${(rec.morning_progress / rec.morning_total) * 100}%`;
              const eveningWidth = `${(rec.evening_progress / rec.evening_total) * 100}%`;

              return (
                <div className="surgery" key={rec.id} style={{ marginBottom: '28px' }}>
                  <div className="surgery-header-row">
                    <div className="surgery-info">
                      <span className="surgery-indicator"></span>

                      <span className="surgery-label">
                        {`${getSurgeryDisplayName(rec.surgery)} • ${rec.side.charAt(0).toUpperCase() + rec.side.slice(1)
                          } Side • Week ${rec.current_week}`}
                      </span>
                    </div>

                    <button
                      className="delete-path-btn"
                      onClick={() => handleRemoveRecovery(rec.id)}
                    >
                      Delete Path
                    </button>
                  </div>
                  <div className="session-grid">
                    {/* Morning Session */}
                    <div className={morningDetails.cardClass}>
                      <div className="session-top">
                        <div>
                          <h3><i className="fa-solid fa-sun"></i> Morning</h3>
                          <span><i className="fa-regular fa-clock"></i> Anytime</span>
                        </div>
                        <span className={morningDetails.badgeClass}>{morningDetails.badgeText}</span>
                      </div>
                      <div className="progress-info">{rec.morning_progress} / {rec.morning_total} Exercises</div>
                      <div className="progress-bar">
                        <div className="progress-fill morning-fill" style={{ width: morningWidth }}></div>
                      </div>
                      <button
                        className={morningDetails.disabled ? "secondary-btn" : "primary-btn"}
                        disabled={morningDetails.disabled}
                        onClick={() => openExercise(rec.id, 'morning', rec.surgery)}
                      >
                        {morningDetails.btnText}
                      </button>
                    </div>

                    {/* Evening Session */}
                    <div className={eveningDetails.cardClass}>
                      <div className="session-top">
                        <div>
                          <h3><i className="fa-solid fa-moon"></i> Evening</h3>
                          <span><i className="fa-regular fa-clock"></i> 2h cooldown after Morning</span>
                        </div>
                        <span className={eveningDetails.badgeClass}>{eveningDetails.badgeText}</span>
                      </div>
                      <div className="progress-info">{rec.evening_progress} / {rec.evening_total} Exercises</div>
                      <div className="progress-bar">
                        <div className="progress-fill evening-fill" style={{ width: eveningWidth }}></div>
                      </div>
                      <button
                        className={eveningDetails.disabled ? "secondary-btn" : "primary-btn"}
                        disabled={eveningDetails.disabled}
                        onClick={() => openExercise(rec.id, 'evening', rec.surgery)}
                      >
                        {eveningDetails.btnText}
                      </button>
                    </div>
                  </div>
                </div>
              );
            })
          )}

          <div className="section-divider"></div>

          <div className="daily-progress">
            <div>
              <h3>Daily Progress</h3>
              <p>{completedExercises} / {totalExercises} Exercises Completed</p>
            </div>
            <div className="daily-right">
              <span>{progressPercent}%</span>
              <div className="daily-progress-bar">
                <div className="daily-fill" style={{ width: `${progressPercent}%` }}></div>
              </div>
            </div>
          </div>
        </section>

        <button className="hero-card-past" onClick={() => navigate("/sessions")}>
          View Past Sessions
        </button>

        <section id="progress-part">
          <div className="recovery-progress">Recovery Progress</div>
          <div className="progress-container">
            <Body activeRecoveries={activeRecoveries} />
            <div className="right-section">
              <div className="top-row">
                <div className="middle-progress-section">
                  <div className="xp">
                    Total XP : {currentXp}
                  </div>
                  <div className="league">
                    <img
                      src={leagueImages[getLeague(currentXp)]}
                      className="league-img"
                      alt="League Badge"
                    />
                  </div>
                </div>

                <div className="add-surgery-card">
                  <h3>
                    <i className="fa-solid fa-plus"></i>
                    Add New Recovery
                  </h3>

                  <label>Surgery</label>
                  <select
                    id="surgerySelect"
                    value={selectedSurgery}
                    onChange={(e) => setSelectedSurgery(e.target.value)}
                  >
                    <optgroup label="Shoulder">
                      <option value="rotatorCuffRepair">Rotator Cuff Repair</option>
                      <option value="frozenShoulder">Frozen Shoulder</option>
                      <option value="shoulderArthroscopy">Shoulder Arthroscopy</option>
                      <option value="shoulderReplacement">Shoulder Replacement</option>
                      <option value="labrumRepair">Labrum Repair</option>
                    </optgroup>

                    <optgroup label="Elbow">
                      <option value="tennisElbow">Tennis Elbow</option>
                      <option value="golferElbow">Golfer's Elbow</option>
                      <option value="elbowArthroscopy">Elbow Arthroscopy</option>
                      <option value="distalBicepsRepair">Distal Biceps Repair</option>
                      <option value="tricepsRepair">Triceps Repair</option>
                    </optgroup>

                    <optgroup label="Knee">
                      <option value="aclReconstruction">ACL Reconstruction</option>
                      <option value="meniscusRepair">Meniscus Repair</option>
                      <option value="kneeReplacement">Knee Replacement</option>
                      <option value="patellarRepair">Patellar Repair</option>
                    </optgroup>
                  </select>

                  <label>Affected Side</label>
                  <div className="side-selector">
                    <button
                      className={`side-btn ${selectedSide === 'left' ? 'active' : ''}`}
                      onClick={() => setSelectedSide('left')}
                    >
                      Left
                    </button>
                    <button
                      className={`side-btn ${selectedSide === 'right' ? 'active' : ''}`}
                      onClick={() => setSelectedSide('right')}
                    >
                      Right
                    </button>
                  </div>

                  <button className="add-btn" onClick={handleAddRecovery}>
                    + Add Recovery
                  </button>
                </div>
              </div>

              <div className="week-map-card">
                <div className="week-legend">
                  <div className="week-item">
                    <span className="color week1"></span>
                    <p>Week {currentWeek}</p>
                  </div>
                  <div className="week-item">
                    <span className="color week2"></span>
                    <p>Week 2</p>
                  </div>
                  <div className="week-item">
                    <span className="color week3"></span>
                    <p>Week 3</p>
                  </div>
                  <div className="week-item">
                    <span className="color week4"></span>
                    <p>Week 4</p>
                  </div>
                  <div className="week-item">
                    <span className="color week5"></span>
                    <p>Week 5</p>
                  </div>
                  <div className="week-item">
                    <span className="color week6"></span>
                    <p>Week 6</p>
                  </div>
                  <div className="week-item">
                    <span className="color week7"></span>
                    <p>Week 7</p>
                  </div>
                  <div className="week-item">
                    <span className="color week8"></span>
                    <p>Recovered</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <div style={{ textAlign: 'center', marginTop: '20px' }}>
          <button className="primary-btn" onClick={() => openExercise(null, null, 'rotatorCuffRepair')} style={{ padding: '12px 28px' }}>
            Quick Start: Side Arm Raise
          </button>
        </div>
      </main>

      <ExerciseModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        exercises={currentExercises}
        challenges={currentChallenges}
        onComplete={handleSessionComplete}
        onAwardXp={handleAwardXp}
        onExerciseComplete={handleExerciseComplete}
        recovery={activeRecoveries.find(r => r.id === activeExerciseSession?.recoveryId)}
        sessionType={activeExerciseSession?.sessionType}
        userId={user?.id}
        onChallengeComplete={handleChallengeComplete}
      />
    </>
  );
}