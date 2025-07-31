import { Engine }           from "../gameEngine/core/Engine.js";
import { Ball } from "./Ball.js";
import { Paddle } from "./Paddle.js";
const engine = new Engine("gameCanvas",window.innerWidth,window.innerHeight);

const middleHeight=window.innerHeight/2;
const middleWidth=window.innerWidth/2;

const ballRadius=5;
const startSpeed=10;


const paddleWidth=3;
const paddleHeight=50;
const paddleSideMarginSpace=20;
const paddleSpeed=10;


const ball=new Ball(middleWidth,middleHeight,ballRadius,"white",startSpeed);

const paddle=new Paddle(paddleSideMarginSpace,middleHeight,paddleWidth,paddleHeight,"white",paddleSpeed);
const paddle2=new Paddle(window.innerWidth-paddleSideMarginSpace,middleHeight,paddleWidth,paddleHeight,"white",paddleSpeed);

engine.addObject(ball);
engine.addObject(paddle);
engine.addObject(paddle2);

engine.start();