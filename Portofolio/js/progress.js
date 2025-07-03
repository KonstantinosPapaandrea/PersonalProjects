window.addEventListener("scroll", function() {
  const scrollPercent = (window.scrollY / (document.documentElement.scrollHeight - window.innerHeight)) * 100;
  document.querySelector('.progress-bar-filled').style.width = scrollPercent + '%';
});
document.addEventListener('DOMContentLoaded', () => {
  const nextBtns = document.querySelectorAll('.next-btn');  // Get all "next" links
  const sections = document.querySelectorAll('.section');   // Get all sections
  let passedSections = [];  // Array to track which sections have been passed

  // Function to show the "Level Up!" message
  function showLevelUp() {
    const levelUpMessage = document.createElement('div');
    levelUpMessage.classList.add('level-up');
    levelUpMessage.textContent = "Level Up!";
    
    // Append to body
    document.body.appendChild(levelUpMessage);
    
    // Remove the message after the animation ends
    setTimeout(() => {
      levelUpMessage.remove();
    }, 1500); // Remove after 1.5s (duration of the animation)
  }

  // Enable the link for the next section after leveling up
  function enableNextLink(index) {
    if (!passedSections.includes(sections[index])) {
      passedSections.push(sections[index]);
      nextBtns[index].disabled = false;  // Enable the next link for this section
      nextBtns[index].style.pointerEvents = 'auto'; // Enable interaction
      nextBtns[index].style.opacity = '1'; // Restore opacity
    }
  }

  // Event listener for .next-btn
  nextBtns.forEach((btn, index) => {
    btn.addEventListener('click', () => {
      const section = sections[index];  // Get the section corresponding to the clicked link
      
      // Check if this section has already been passed
      if (passedSections.includes(section)) {
        console.log("Already leveled up this section!");
        return; // Do nothing if the section is already passed
      }

      // Mark the section as passed
      passedSections.push(section);

      // Trigger the level-up message animation
      showLevelUp();

      // Enable the next section's link once this one is unlocked
      enableNextLink(index + 1);  // Enable the link for the next section
    });
  });
});
