// physics‑game.js
import { levels } from './levels.js';

const { Engine, Render, World, Bodies, Body, Events } = Matter;

export class Game {
  constructor(canvasId, startLevel = 0) {
    // 1) create engine & world
    this.engine = Engine.create();
    this.world  = this.engine.world;

    // 2) wire up renderer
    this.render = Render.create({
      element: document.body,
      canvas:   document.getElementById(canvasId),
      engine:   this.engine,
      options: {
        width:  window.innerWidth,
        height: window.innerHeight,
        wireframes: false,
        background: '#000'
      }
    });

    // 3) static boundaries
    const w = window.innerWidth, h = window.innerHeight;
    World.add(this.world, [
      Bodies.rectangle(w/2, -10, w, 20, { isStatic: true }),    // top
      Bodies.rectangle(-10, h/2, 20, h, { isStatic: true }),    // left
      Bodies.rectangle(w+10, h/2, 20, h, { isStatic: true })    // right
    ]);

    // 4) create paddle as a kinematic body
    this.paddle = Bodies.rectangle(
      w/2, h - 30, 160, 20,
      { isStatic: true, label: 'paddle' }
    );
    World.add(this.world, this.paddle);

    // 5) event handling: remove breakable blocks, spawn power‑ups
    Events.on(this.engine, 'collisionStart', evt => {
      for (let pair of evt.pairs) {
        const { bodyA, bodyB } = pair;
        // detect ball vs block
        if (bodyA.label === 'ball' && bodyB.label === 'block') {
          this._breakBlock(bodyB);
        } else if (bodyB.label === 'ball' && bodyA.label === 'block') {
          this._breakBlock(bodyA);
        }
      }
    });

    // 6) prepare level
    this.currentLevel = startLevel;
    this._loadLevel(this.currentLevel);

    // 7) listen for resize
    window.addEventListener('resize', () => {
      Render.lookAt(this.render, { min: {x:0,y:0}, max:{x:window.innerWidth,y:window.innerHeight} });
    });
  }

  _loadLevel(idx) {
    // clear old blocks
    World.clear(this.world, false);
    // re‑add boundaries & paddle
    World.add(this.world, this.paddle);
    // spawn ball(s)
    const ball = Bodies.circle(
      window.innerWidth/2, window.innerHeight/2, 15,
      { restitution: 1, label: 'ball' }
    );
    World.add(this.world, ball);

    // build blocks from levels[idx].layout
    const layout = levels[idx].layout;
    const rows = layout.length, cols = layout[0].length;
    const pad = 10;
    const blockW = (window.innerWidth - (cols+1)*pad)/cols;
    const blockH = blockW;
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const code = layout[r][c];
        if (!code) continue;
        const breakable = code===1;
        const block = Bodies.rectangle(
          pad + c*(blockW+pad) + blockW/2,
          pad + r*(blockH+pad) + blockH/2,
          blockW, blockH,
          {
            isStatic: true,
            label: 'block',
            render: { fillStyle: breakable ? '#e74c3c' : '#7f8c8d' }
          }
        );
        block.breakable = breakable;
        World.add(this.world, block);
      }
    }
  }

  _breakBlock(block) {
    if (block.breakable) {
      World.remove(this.world, block);
      // 20% chance spawn x2 powerup (you’d create another body)
    }
  }

  start() {
    Engine.run(this.engine);
    Render.run(this.render);
  }
}
