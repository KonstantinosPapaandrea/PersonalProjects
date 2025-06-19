import React from 'react';
import '../styles/Section.css';

function Hero({ parallaxRef }) {
  return (
    <section className="section hero">
      <h1>Constantinos Papaandrea</h1>
      <p>Game Developer • Full-stack Enthusiast • CS Student</p>

      <div className="hero-buttons">
        <button
          className="btn"
          onClick={() => parallaxRef?.current?.scrollTo(3)}
        >
          Hire Me
        </button>
        <button
          className="btn btn-secondary"
          onClick={() => parallaxRef?.current?.scrollTo(1)}
        >
          About Me
        </button>
      </div>
    </section>
  );
}

export default Hero;
