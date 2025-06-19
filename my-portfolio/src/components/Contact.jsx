// src/components/Contact.jsx
import React from 'react';
import '../styles/Section.css';

function Contact({ parallaxRef }) {
  return (
    <section className="section contact"  style={{
    backgroundImage: "url('https://images.unsplash.com/photo-1506765515384-028b60a970df?auto=format&fit=crop&w=1400&q=80')"
  }}>
      <h2>📬 Contact Me</h2>

      <div className="contact-info">
        <p><strong>Name:</strong> Constantinos Papaandrea</p>
        <p><strong>Email:</strong> <a href="mailto:your@email.com">your@email.com</a></p>
        <p><strong>Phone:</strong> +123 456 7890</p>
        <p><strong>Location:</strong> City, Country</p>
      </div>

      <div className="contact-links">
        <h3>🔗 Find me online</h3>
        <ul>
          <li><a href="https://github.com/yourusername" target="_blank">GitHub</a></li>
          <li><a href="https://linkedin.com/in/yourusername" target="_blank">LinkedIn</a></li>
          <li><a href="https://yourportfolio.com/resume.pdf" target="_blank">Download Résumé</a></li>
        </ul>
      </div>

      {/* ⬇️ Back to Top Button */}
      <button
        className="btn back-to-top"
        onClick={() => parallaxRef?.current?.scrollTo(0)}
      >
        ↑ Back to Top
      </button>
    </section>
  );
}

export default Contact;
