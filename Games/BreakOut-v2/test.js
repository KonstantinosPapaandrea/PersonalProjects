console.log("✅ Main script started");

const worker = new Worker(new URL("./physicsWorker.js", import.meta.url), { type: "module" });

worker.onmessage = (e) => {
  console.log("✅ Main received:", e.data);
};

worker.postMessage({ test: "hello" });
