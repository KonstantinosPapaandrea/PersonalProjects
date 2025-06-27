/* ----------------------------------------------------------
   3-D wheel – STEP 1 : place + log every card
---------------------------------------------------------- */
(function(){

    /* grab the wheel & cards */
    const wheel  = document.getElementById('projectWheel');
    const cards  = [...wheel.querySelectorAll('.wheel__card')];
    const total  = cards.length;
  
    /* save card-count as a CSS custom property so
       your existing CSS ( --count ) still works     */
    wheel.style.setProperty('--count', total);
  
    /* geometry: angle & radius MUST match the CSS values */
    const angle  = 360 / total;            // in degrees
    const radius = parseFloat(
                     getComputedStyle(wheel)
                     .getPropertyValue('--radius')
                   );                      // already in px
  
    /* loop through every card, assign coordinate & log it */
    cards.forEach( (card, i) => {
  
      /* ① store index on the element for later use */
      card.dataset.idx = i;                  // shows via the ::after label
  
      /* ② write the transform inline so we SEE it immediately */
      card.style.transform =
        `rotateY(${i * angle}deg)
         translateZ(${radius}px)
         translate(-50%, -50%)`;
  
      /* ③ console log for verification */
      console.log(
        `Card ${i}:  rotateY(${i * angle}°)  translateZ(${radius}px)`
      );
    });
  
    /* that’s it – every card now sits on the rim of
       an invisible wheel; they’re all visible & labelled */
  })();
  