// Charts for CTF Platform

document.addEventListener('DOMContentLoaded', function() {
    // Only run charts code if the page contains chart elements
    if (document.getElementById('scoreChart') || 
        document.getElementById('submissionsChart') || 
        document.getElementById('challengeTypesChart')) {
        initCharts();
    }
});

function initCharts() {
    // Helper function to get random colors
    function getRandomColor() {
        const letters = '0123456789ABCDEF';
        let color = '#';
        for (let i = 0; i < 6; i++) {
            color += letters[Math.floor(Math.random() * 16)];
        }
        return color;
    }
    
    // Generate array of random colors
    function generateColors(count) {
        const colors = [];
        for (let i = 0; i < count; i++) {
            colors.push(getRandomColor());
        }
        return colors;
    }

    // Score over time chart (if element exists)
    const scoreChartEl = document.getElementById('scoreChart');
    if (scoreChartEl) {
        const scoreData = JSON.parse(scoreChartEl.getAttribute('data-scores') || '[]');
        
        if (scoreData.length > 0) {
            const ctx = scoreChartEl.getContext('2d');
            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: scoreData.map(item => item.date),
                    datasets: [{
                        label: 'Score Progress',
                        data: scoreData.map(item => item.score),
                        backgroundColor: 'rgba(75, 192, 192, 0.2)',
                        borderColor: 'rgba(75, 192, 192, 1)',
                        borderWidth: 2,
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    },
                    plugins: {
                        title: {
                            display: true,
                            text: 'Score Progress Over Time'
                        }
                    }
                }
            });
        } else {
            scoreChartEl.innerHTML = '<div class="text-center p-4">No score data available yet</div>';
        }
    }
    
    // Submissions by category chart (if element exists)
    const submissionsChartEl = document.getElementById('submissionsChart');
    if (submissionsChartEl) {
        const submissionsData = JSON.parse(submissionsChartEl.getAttribute('data-submissions') || '{}');
        
        if (Object.keys(submissionsData).length > 0) {
            const ctx = submissionsChartEl.getContext('2d');
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: Object.keys(submissionsData),
                    datasets: [{
                        label: 'Correct Submissions',
                        data: Object.values(submissionsData).map(item => item.correct),
                        backgroundColor: 'rgba(75, 192, 192, 0.5)',
                        borderColor: 'rgba(75, 192, 192, 1)',
                        borderWidth: 1
                    }, {
                        label: 'Incorrect Submissions',
                        data: Object.values(submissionsData).map(item => item.incorrect),
                        backgroundColor: 'rgba(255, 99, 132, 0.5)',
                        borderColor: 'rgba(255, 99, 132, 1)',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            stacked: false
                        },
                        x: {
                            stacked: false
                        }
                    },
                    plugins: {
                        title: {
                            display: true,
                            text: 'Submissions by Challenge Type'
                        }
                    }
                }
            });
        } else {
            submissionsChartEl.innerHTML = '<div class="text-center p-4">No submission data available yet</div>';
        }
    }
    
    // Challenge types distribution chart (if element exists)
    const challengeTypesChartEl = document.getElementById('challengeTypesChart');
    if (challengeTypesChartEl) {
        const typesData = JSON.parse(challengeTypesChartEl.getAttribute('data-types') || '{}');
        
        if (Object.keys(typesData).length > 0) {
            const labels = Object.keys(typesData);
            const values = Object.values(typesData);
            const backgroundColors = generateColors(labels.length);
            
            const ctx = challengeTypesChartEl.getContext('2d');
            new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: labels,
                    datasets: [{
                        data: values,
                        backgroundColor: backgroundColors,
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        title: {
                            display: true,
                            text: 'Challenge Types Distribution'
                        }
                    }
                }
            });
        } else {
            challengeTypesChartEl.innerHTML = '<div class="text-center p-4">No challenge data available yet</div>';
        }
    }
    
    // Leaderboard competition chart (if element exists)
    const leaderboardChartEl = document.getElementById('leaderboardChart');
    if (leaderboardChartEl) {
        const leaderboardData = JSON.parse(leaderboardChartEl.getAttribute('data-leaderboard') || '[]');
        
        if (leaderboardData.length > 0) {
            const ctx = leaderboardChartEl.getContext('2d');
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: leaderboardData.map(item => item.username),
                    datasets: [{
                        label: 'Score',
                        data: leaderboardData.map(item => item.score),
                        backgroundColor: 'rgba(54, 162, 235, 0.5)',
                        borderColor: 'rgba(54, 162, 235, 1)',
                        borderWidth: 1
                    }]
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            beginAtZero: true
                        }
                    },
                    plugins: {
                        title: {
                            display: true,
                            text: 'Top Players'
                        }
                    }
                }
            });
        } else {
            leaderboardChartEl.innerHTML = '<div class="text-center p-4">No leaderboard data available yet</div>';
        }
    }
}
