const WebSocket = require('ws');

// Use the PORT env var that Render sets for you
const port = process.env.PORT || 3000;
const wss = new WebSocket.Server({ port }, () => {
  console.log(`WebSocket server running on port ${port}`);
});

wss.on('connection', (ws) => {
  console.log('Client connected');
  // Echo back any message
  ws.on('message', (msg) => {
    console.log(`Received: ${msg}`);
    ws.send(`Echo: ${msg}`);
  });
  ws.on('close', () => console.log('Client disconnected'));
});
