/* ─── Skills data – edit here ────────────────────────────────── */
const skillLabels = [
  'HTML','CSS','JavaScript', 'React',
  , 'C# / Unity', 'SQL','Java','C','ASM','Parallelism','Algorithms','GitHub'
];

const skillScores = [95, 90, 80, 70, 90, 90,95,80,75,80,90,95,95]; // 0–100 scale

/* ─── Build the neon radar chart ─────────────────────────────── */
const ctx = document.getElementById('skillRadar');

if (ctx) {
  new Chart(ctx, {
    type: 'radar',
    data: {
      labels: skillLabels,
      datasets: [{
        label: 'Proficiency (%)',
        data: skillScores,
        fill: true,
        backgroundColor: 'hsla(198,100%,60%,0.08)',
        borderColor:  'hsl(198 100% 60%)',
        borderWidth: 2,
        pointBackgroundColor: 'hsl(198 100% 60%)',
        pointRadius: 4
    
      }]
    },
    options: {
            layout: { padding: 30 },

      responsive: true,
      maintainAspectRatio: false,
      scales: {
        r: {
          suggestedMin: 0,
          suggestedMax: 100,
          angleLines: { color: '#233' },
          grid:       { color: '#233' },
          pointLabels:{ color: '#9cf', font:{size:14} },
          ticks:      { display:false }
        }
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#0b3d91',
          borderColor: 'hsl(198 100% 60%)',
          borderWidth: 1,
          titleColor: '#fff',
          bodyColor: '#fff'
        }
      }
    }
  });
}
/* ==================================================================
   Inter-icon hover → update the info panel
   ================================================================== */
const infoLabel = document.getElementById('skillLabel');
const infoBlurb = document.getElementById('skillBlurb');
const iconItems = document.querySelectorAll('#skillList li');

iconItems.forEach(li=>{
  li.addEventListener('mouseenter', ()=>updateInfo(li));
  li.addEventListener('focus',     ()=>updateInfo(li)); // keyboard
});

function updateInfo(el){
  infoLabel.textContent = el.dataset.skill;
  infoBlurb.innerHTML   = el.dataset.blurb;   // safe – our own strings
}

/* start with the first item selected */
updateInfo(iconItems[0]);
