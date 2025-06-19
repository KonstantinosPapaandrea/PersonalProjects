// About.jsx
import React from 'react';
import '../styles/Section.css';

function About({ parallaxRef }) {
  return (
    <section className="section about">
      <h2>About Me</h2>
      <p>This is the About section. Tell your story here.</p>

      <button
        className="btn next-button"
        onClick={() => parallaxRef?.current?.scrollTo(2)}
      >
        ↓ Next
      </button>
    </section>
  );
}

export default About;
