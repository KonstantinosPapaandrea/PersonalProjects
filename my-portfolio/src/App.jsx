// App.jsx
import React, { useState } from "react";
import { useTransition, animated, useSpring } from "@react-spring/web";
import sections from "./data/sections";
import "./styles/App.css";

function App() {
  const [index, setIndex] = useState(0);

const transitions = useTransition(index, {
  from: { opacity: 0, transform: "translate3d(0, 100px, 0)" },
  enter: { opacity: 1, transform: "translate3d(0, 0, 0)" },
  leave: { opacity: 0, transform: "translate3d(0, -100px, 0)" },
  config: { tension: 170, friction: 26 }
});


  const bgSpring = useSpring({
    transform: `scale(${1 + index * 0.05})`,
    config: { mass: 1, tension: 120, friction: 40 }
  });

  const next = () => setIndex((prev) => (prev + 1) % sections.length);

  return (
    <div className="App">
      <animated.div className="background" style={bgSpring} />

      <div className="content">
        {transitions((style, i) => (
          <animated.div className="card" style={style}>
            <h1>{sections[i].title}</h1>
            <p>{sections[i].subtitle}</p>
            <button className="btn" onClick={next}>
              {sections[i].action}
            </button>
          </animated.div>
        ))}
      </div>
    </div>
  );
}

export default App;