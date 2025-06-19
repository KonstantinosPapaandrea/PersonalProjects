// src/components/Project.jsx
import React from 'react';
import '../styles/Section.css';

function Project({ parallaxRef }) {
  return (
    <section className="section projects"  style={{
    backgroundImage: "url('https://images.unsplash.com/photo-1581092588420-1acb3519114b?auto=format&fit=crop&w=1400&q=80')"
  }}>
      <h2>🚀 Projects</h2>

      <div className="projects-container">
        <div className="project-card">
          <h3>🎮 Game Engine Demo</h3>
          <p>A 2D game engine built with C++ and SDL2. Includes physics and level editor.</p>
          <a href="https://github.com/yourusername/game-engine-demo" target="_blank" className="btn">View on GitHub</a>
        </div>

        <div className="project-card">
          <h3>🖥️ PC Builder AI Tool</h3>
          <p>Helps users build the perfect PC using AI based on budget & use case.</p>
          <a href="https://your-website.com/pc-builder" target="_blank" className="btn">Live Demo</a>
        </div>

        <div className="project-card">
          <h3>📱 Portfolio Website</h3>
          <p>This website! Built with React, Vite, and Parallax Spring animations.</p>
          <a href="https://github.com/yourusername/portfolio" target="_blank" className="btn">Source Code</a>
        </div>
      </div>

      <button
        className="btn next-button"
        onClick={() => parallaxRef?.current?.scrollTo(3)}
      >
        ↓ Next
      </button>
    </section>
  );
}

export default Project;
