import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime


cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)

db = firestore.client()


db.collection("users").document("demo_user").set
({
    "name": "Demo User",
    "gmail": "demo@gmail.com",
    "age": 25,
    "gender": "Female",
    "createdAt": firestore.SERVER_TIMESTAMP,
    "currentSurgery": "surgery001",
    "totalXP": 0,
    "coins": 0,
    "level": 1,
    "currentStreak": 0,
    "lastLogin": firestore.SERVER_TIMESTAMP,
    "profilePic": ""
})


db.collection("surgeries").document("surgery001").set
({
    "uid": "demo_user",
    "surgeryType": "rotator_cuff",
    "doctor": "",
    "hospital": "",
    "startDate": firestore.SERVER_TIMESTAMP,
    "currentWeek": 1,
    "status": "active",
    "completion": 0,
    "totalSessions": 0,
    "averageScore": 0
})


exercise_catalog = [

    {
        "exerciseId":"side_arm_raise",
        "name":"Side Arm Raise",
        "launcherKey":"side_arm_raise",
        "category":"exercise",
        "description":"Basic shoulder abduction exercise",
        "surgeries":["rotator_cuff"],
        "difficulty":"Easy",
        "estimatedTime":5,
        "rewardXP":20,
        "rewardCoins":10,
        "unlockConditions":{
            "minWeek":1,
            "maxWeek":6,
            "daily":True,
            "availableDays":[]
        }
    },

    {
        "exerciseId":"forgotten_orchestra",
        "name":"Forgotten Orchestra",
        "launcherKey":"forgotten_orchestra",
        "category":"exercise",
        "description":"Gamified ROM exercise",
        "surgeries":["rotator_cuff"],
        "difficulty":"Medium",
        "estimatedTime":10,
        "rewardXP":50,
        "rewardCoins":30,
        "unlockConditions":{
            "minWeek":1,
            "maxWeek":6,
            "daily":True,
            "availableDays":[]
        }
    },

    {
        "exerciseId":"paint_the_object",
        "name":"Paint The Object",
        "launcherKey":"paint_the_object",
        "category":"challenge",
        "description":"Weekend painting challenge",
        "surgeries":["rotator_cuff"],
        "difficulty":"Hard",
        "estimatedTime":15,
        "rewardXP":80,
        "rewardCoins":40,
        "unlockConditions":{
            "minWeek":2,
            "maxWeek":6,
            "left_hand_hold":30,
            "right_hand_hold":30,
            "daily":False,
            "weekendOnly":True,
            "availableDays":["Saturday","Sunday"],
            "minAverageScore":80,
            "requiredExercises":[
                "side_arm_raise",
                "forgotten_orchestra"
            ]
        }
    },
    {
        "exerciseId":"belle_pose",
        "name":"Copy the pose",
        "launcherKey":"belle_pose",
        "category":"challenge",
        "description":"Weekend dance challenge",
        "surgeries":["rotator_cuff"],
        "difficulty":"Hard",
        "estimatedTime":15,
        "rewardXP":80,
        "rewardCoins":40,
        "unlockConditions":{
            "minWeek":3,
            "maxWeek":6,
            "left_hand_hild":30,
            "right_hand_hold":30,
            "daily":False,
            "weekendOnly":True,
            "availableDays":["Saturday","Sunday"],
            "minAverageScore":80,
            "requiredExercises":[
                "side_arm_raise",
                "forgotten_orchestra"
            ]
        }
    },
    {
        "exerciseId":"leg_raise",
        "name":"Leg Raise",
        "launcherKey":"leg_raise",
        "category":"exercise",
        "description":"Perform controlled straight leg raises to improve lower limb strength and mobility.",
        "surgeries":["acl","knee_replacement","meniscus_repair"],
        "difficulty":"Easy",
        "estimatedTime":5,
        "rewardXP":20,
        "rewardCoins":10,
        "unlockConditions":{
            "minWeek":1,
            "maxWeek":4,
            "daily":True,
            "weekendOnly":False,
            "availableDays":[],
            "minAverageScore":0,
            "requiredExercises":[]
        }
    },
    {
        "exerciseId":"gaumukhasana",
        "name":"Gaumukhasana Stretch",
        "launcherKey":"gaumukhasana",
        "category":"exercise",
        "description":"Improve shoulder abduction and flexibility using the Gaumukhasana arm position.",
        "surgeries":["rotator_cuff","shoulder_replacement","shoulder_abduction"],
        "difficulty":"Medium",
        "estimatedTime":8,
        "rewardXP":35,
        "rewardCoins":20,
        "unlockConditions":{
            "minWeek":2,
            "maxWeek":6,
            "daily":True,
            "weekendOnly":False,
            "availableDays":['Monday','Wednesday','Friday'],
            "minAverageScore":0,
            "requiredExercises":["side_arm_raise",
                "forgotten_orchestra"]
        }
    },
    {
        "exerciseId":"oceanic_waves",
        "name":"Oceanic Waves",
        "launcherKey":"oceanic_waves",
        "category":"game",
        "description":"Perform rhythmic arm raises to create calming ocean waves while improving shoulder mobility.",
        "surgeries":["rotator_cuff","shoulder_replacement","shoulder_abduction"],
        "difficulty":"Medium",
        "estimatedTime":10,
        "rewardXP":50,
        "rewardCoins":25,
        "unlockConditions":{
            "minWeek":3,
            "maxWeek":6,
            "daily":False,
            "weekendOnly":True,
            "availableDays":['Sunday'],
            "minAverageScore":70,
            "requiredExercises":[
                "gaumukhasana","side_arm_raise",
                "forgotten_orchestra"
            ]
        }
    }
]

for ex in exercise_catalog:
    db.collection("exerciseCatalog").document(ex["exerciseId"]).set(ex)


db.collection("sessions").document("session001").set({
    "uid":"demo_user",
    "surgeryId":"surgery001",
    "date":firestore.SERVER_TIMESTAMP,
    "startTime":firestore.SERVER_TIMESTAMP,
    "endTime":firestore.SERVER_TIMESTAMP,
    "duration":0
})


db.collection("exerciseResults").document("result001").set({
    "uid":"demo_user",
    "sessionId":"session001",
    "exerciseId":"side_arm_raise",
    "completed":False,
    "score":0,
    "xpEarned":0,
    "coinsEarned":0,
    "metrics":{},
    "timestamp":firestore.SERVER_TIMESTAMP
})



db.collection("achievements").document("demo").set({
    "uid":"demo_user",
    "achievement":"Welcome to RehabVerse",
    "date":firestore.SERVER_TIMESTAMP
})

print("Firestore seeded successfully!")