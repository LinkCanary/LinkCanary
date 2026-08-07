import { toNodeHandler } from "better-auth/node";
import { createServer } from "node:http";
import { auth } from "./auth.js";

const port = Number(process.env.PORT || 3001);

const server = createServer(toNodeHandler(auth));

server.listen(port, "0.0.0.0", () => {
  console.log(`Better Auth running on :${port}`);
});
