

const defaultColor = "#41857c";

const surgeryMap = {

    // SHOULDER
    rotatorCuffRepair: {
        left: ["left-shoulder"],
        right: ["right-shoulder"]
    },

    frozenShoulder: {
        left: ["left-shoulder"],
        right: ["right-shoulder"]
    },

    shoulderArthroscopy: {
        left: ["left-shoulder"],
        right: ["right-shoulder"]
    },

    shoulderReplacement: {
        left: ["left-shoulder"],
        right: ["right-shoulder"]
    },

    labrumRepair: {
        left: ["left-shoulder"],
        right: ["right-shoulder"]
    },

    // ELBOW
    tennisElbow: {
        left: ["left-arm"],
        right: ["right-arm"]
    },

    golferElbow: {
        left: ["left-arm"],
        right: ["right-arm"]
    },

    elbowArthroscopy: {
        left: ["left-arm"],
        right: ["right-arm"]
    },

    distalBicepsRepair: {
        left: ["left-arm"],
        right: ["right-arm"]
    },

    tricepsRepair: {
        left: ["left-arm"],
        right: ["right-arm"]
    },

    // LEG
    aclReconstruction: {
        left: ["left-leg"],
        right: ["right-leg"]
    },

    meniscusRepair: {
        left: ["left-leg"],
        right: ["right-leg"]
    },

    kneeReplacement: {
        left: ["left-leg"],
        right: ["right-leg"]
    },

    patellarRepair: {
        left: ["left-leg"],
        right: ["right-leg"]
    }

};
const weekColors = {
    1: "#ff4d4d",
    2: "#ff884d",
    3: "#ffd24d",
    4: "#d8e95f",
    5: "#8dd96d",
    6: "#4ecdc4",
    7: "#2ea8a1",
    8: "#41857c"
};
function resetBody() {
    document.querySelectorAll(".human-body svg path").forEach(path => {
        path.style.fill = defaultColor;
    });
}
function highlightBody(surgery, side, week) {
    resetBody();
    const bodyParts = surgeryMap[surgery]?.[side];
    if (!bodyParts) return;
    const color = weekColors[Number(week)];
    bodyParts.forEach(part => {
        const svg = document.getElementById(part);
        if (svg) {
            svg.querySelector("path").style.fill = color;
        }
    });
}
highlightBody(
    "rotatorCuffRepair",
    "left",
    3
);