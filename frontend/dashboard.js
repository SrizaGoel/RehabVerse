const sections = document.querySelectorAll("section[id]");
const navLinks = document.querySelectorAll(".nav-links a");
window.addEventListener("scroll", () => {
    let current = "";
    sections.forEach(section => {
        const sectionTop = section.offsetTop - 120;
        const sectionHeight = section.offsetHeight;
        if (window.scrollY >= sectionTop &&
            window.scrollY < sectionTop + sectionHeight) {
            current = section.getAttribute("id");
        }
    });
    navLinks.forEach(link => {
        link.classList.remove("active");
        if (link.getAttribute("href") === "#" + current) {
            link.classList.add("active");
        }
    });
});
function updateSessions() {
    const now = new Date();
    const currentMinutes =
        now.getHours() * 60 + now.getMinutes();
    const MORNING_START = 4 * 60;
    const MORNING_END = 12 * 60;
    const EVENING_START = 16 * 60;
    const EVENING_END = 20 * 60;
    const cards = document.querySelectorAll(".session-card");
    cards.forEach(card => {
        const isMorning=card.querySelector("h3").textContent.includes("Morning");
        const badge = card.querySelector(".badge");
        const button = card.querySelector("button");
        if (isMorning) {
            if (currentMinutes >= MORNING_START && currentMinutes < MORNING_END ) 
            {
                badge.textContent = "Available";
                badge.className = "badge available";
                button.disabled = false;
                button.textContent = "Continue Session";
                card.classList.remove("locked-card");
                button.classList.remove("secondary-btn");
                button.classList.add("primary-btn");
            }
            else {
                lockMorning(card, badge, button, currentMinutes);
            }
        }
        else {
            if (currentMinutes >= EVENING_START && currentMinutes < EVENING_END) 
            {
                badge.textContent = "Available";
                badge.className = "badge available";
                button.disabled = false;
                button.textContent = "Continue Session";
                card.classList.remove("locked-card");
                button.classList.remove("secondary-btn");
                button.classList.add("primary-btn");
            }
            else {
                lockEvening(card, badge, button, currentMinutes);
            }
        }
    });
}
function formatTime(minutes) {
    const hrs = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hrs}h ${mins}m`;
}
function lockMorning(card, badge, button, now) {
    let remaining;
    if (now < 240) 
    {
        remaining = 240 - now;
    } else 
    {
        remaining = (24 * 60 - now) + 240;
    }
    badge.textContent = formatTime(remaining);
    badge.className = "badge locked";
    button.textContent = "Locked";
    button.disabled = true;
    button.classList.remove("primary-btn");
    button.classList.add("secondary-btn");
    card.classList.add("locked-card");
}
function lockEvening(card, badge, button, now) 
{
    let remaining;
    if (now < 960) 
    {
        remaining = 960 - now;
    }
    else {
        remaining = (24 * 60 - now) + 960;
    }
    badge.textContent = formatTime(remaining);
    badge.className = "badge locked";
    button.textContent = "Locked";
    button.disabled = true;
    button.classList.remove("primary-btn");
    button.classList.add("secondary-btn");
    card.classList.add("locked-card");
}


function updateXP(xp=1000){
    let league;
    if (xp>=0 && xp<=200)
        league=1;
    else if(xp<=745)
        league=2;
    else if(xp<=1499)
        league=3;
    else if(xp<=2499)
        league=4;
    else if(xp<=3999)
        league=5;
    else if(xp<=5999)
        league=6;
    else if(xp<=7999)
        league=7;
    else if(xp<=9999)
        league=8;
    else if(xp<=14999)
        league=9;
    else 
        league=10;
    return league;
}
function updateLeagueImage() {
    const leagueImg = document.getElementById("leagueImg");
    leagueImg.src = `assets/league${updateXP()}.png`;
}
updateSessions();
updateLeagueImage();
setInterval(updateSessions, 60000);