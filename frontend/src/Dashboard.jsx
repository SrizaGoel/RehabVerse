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
  const [activeRecoveries, setActiveRecoveries] = useState([
    {
      id: '1',
      surgery: 'aclReconstruction',
      side: 'left',
      week: 3,
      morningCompleted: false,
      morningCompletedAt: null,
      eveningCompleted: false
    },
    {
      id: '2',
      surgery: 'meniscusRepair',
      side: 'left',
      week: 3,
      morningCompleted: true,
      morningCompletedAt: Date.now() - (60 * 60 * 1000),
      eveningCompleted: false
    }
  ]);

  const [selectedSurgery, setSelectedSurgery] = useState('rotatorCuffRepair');
  const [selectedSide, setSelectedSide] = useState('left');
  const [selectedWeek, setSelectedWeek] = useState(1);

  const [xp, setXp] = useState(0);

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

  const handleAddRecovery = () => {
    const exists = activeRecoveries.some(
      rec => rec.surgery === selectedSurgery && rec.side === selectedSide
    );
    if (!exists) {
      const newRecovery = {
        id: Date.now().toString(),
        surgery: selectedSurgery,
        side: selectedSide,
        week: selectedWeek,
        morningProgress: 0,
        morningTotal: 3,
        morningCompleted: false,
        morningCompletedAt: null,
        eveningProgress: 0,
        eveningTotal: 3,
        eveningCompleted: false
      };
      setActiveRecoveries([...activeRecoveries, newRecovery]);
    } else {
      alert("This recovery is already active!");
    }
  };

  const handleRemoveRecovery = (id) => {
    setActiveRecoveries(activeRecoveries.filter(rec => rec.id !== id));
  };

  const openExercise = (recoveryId, sessionType, surgeryKey) => {
    const program = rehabPrograms[surgeryKey];
    setCurrentExercises(program.exercises);
    setCurrentChallenges(program.challenges);
    setActiveExerciseSession({ recoveryId, sessionType });
    setModalOpen(true);
  };

  const handleSessionComplete = () => {
    if (!activeExerciseSession) return;
    const { recoveryId, sessionType } = activeExerciseSession;

    setActiveRecoveries(prev => prev.map(rec => {
      if (rec.id !== recoveryId) return rec;

      if (sessionType === 'morning') {
        return {
          ...rec,
          morningProgress: rec.morningTotal,
          morningCompleted: true,
          morningCompletedAt: Date.now()
        };
      } else {
        return {
          ...rec,
          eveningProgress: rec.eveningTotal,
          eveningCompleted: true
        };
      }
    }));
  };

  const handleAwardXp = (amount) => {
    setXp(prev => prev + amount);
  };

  // Cooldown & Status Computations for morning session
  const getMorningDetails = (rec) => {
    if (rec.morningCompleted) {
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
    if (rec.eveningCompleted) {
      return {
        badgeText: "Completed",
        badgeClass: "badge completed",
        btnText: "Completed",
        cardClass: "session-card evening-completed",
        disabled: true
      };
    }

    if (!rec.morningCompleted) {
      return {
        badgeText: "Locked",
        badgeClass: "badge locked",
        btnText: "Locked",
        cardClass: "session-card locked-card",
        disabled: true,
        reason: "Waiting for morning session"
      };
    }

    const elapsed = currentTime.getTime() - new Date(rec.morningCompletedAt).getTime();
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

  const totalExercises = activeRecoveries.reduce((sum, rec) => sum + rec.morningTotal + rec.eveningTotal, 0);
  const completedExercises = activeRecoveries.reduce((sum, rec) => sum + rec.morningProgress + rec.eveningProgress, 0);
  const progressPercent = totalExercises > 0 ? Math.round((completedExercises / totalExercises) * 100) : 0;

  const recoveryStatusText = activeRecoveries
    .map(r => `${getSurgeryDisplayName(r.surgery)} (${r.side === 'left' ? 'L' : 'R'})`)
    .join(', ') || 'No active recoveries';

  return (
    <>
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
        <div className="profile">SG</div>
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
              const morningWidth = `${(rec.morningProgress / rec.morningTotal) * 100}%`;
              const eveningWidth = `${(rec.eveningProgress / rec.eveningTotal) * 100}%`;

              return (
                <div className="surgery" key={rec.id} style={{ marginBottom: '28px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <p className="surgery-number">
                      {getSurgeryDisplayName(rec.surgery)} ({rec.side.toUpperCase()}) - Week {rec.week}
                    </p>
                    <button
                      onClick={() => handleRemoveRecovery(rec.id)}
                      style={{
                        border: 'none',
                        background: 'none',
                        color: '#ef4444',
                        cursor: 'pointer',
                        fontSize: '0.85rem',
                        fontWeight: '600'
                      }}
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
                      <div className="progress-info">{rec.morningProgress} / {rec.morningTotal} Exercises</div>
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
                      <div className="progress-info">{rec.eveningProgress} / {rec.eveningTotal} Exercises</div>
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

        <button className="hero-card-past" onClick={() => alert("Past sessions archive coming soon!")}>
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
                    Total XP : {xp}
                  </div>
                  <div className="league">
                    <img
                      src={leagueImages[getLeague(xp)]}
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
                    <p>Week 1</p>
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
        onComplete={handleComplete}
        onAwardXp={handleAwardXp}
      />
    </>
  );

  function handleComplete() {
    handleSessionComplete();
  }
}