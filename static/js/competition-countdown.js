// static/js/competition-countdown.js
// Handles competition countdown timers on the index page

document.addEventListener('DOMContentLoaded', function() {
    // This script expects a global variable COMPETITION_TIMERS to be set by the template
    if (!window.COMPETITION_TIMERS) return;
    window.COMPETITION_TIMERS.forEach(function(timer) {
        const endTime = new Date(timer.end_time).getTime();
        function updateCountdown() {
            const now = new Date().getTime();
            const distance = endTime - now;
            if (distance <= 0) {
                document.getElementById("competition-days-" + timer.id).innerHTML = "0";
                document.getElementById("competition-hours-" + timer.id).innerHTML = "0";
                document.getElementById("competition-mins-" + timer.id).innerHTML = "0";
                return;
            }
            const days = Math.floor(distance / (1000 * 60 * 60 * 24));
            const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
            const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
            document.getElementById("competition-days-" + timer.id).innerHTML = days;
            document.getElementById("competition-hours-" + timer.id).innerHTML = hours;
            document.getElementById("competition-mins-" + timer.id).innerHTML = minutes;
        }
        updateCountdown();
        setInterval(updateCountdown, 60000);
    });
});
