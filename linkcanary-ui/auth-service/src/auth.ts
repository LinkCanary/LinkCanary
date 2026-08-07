import { betterAuth } from "better-auth";
import { Pool } from "pg";

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
});

const socialProviders: Record<string, { clientId: string; clientSecret: string }> = {};

if (process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET) {
  socialProviders.google = {
    clientId: process.env.GOOGLE_CLIENT_ID,
    clientSecret: process.env.GOOGLE_CLIENT_SECRET,
  };
}

if (process.env.GITHUB_CLIENT_ID && process.env.GITHUB_CLIENT_SECRET) {
  socialProviders.github = {
    clientId: process.env.GITHUB_CLIENT_ID,
    clientSecret: process.env.GITHUB_CLIENT_SECRET,
  };
}

const API_URL = process.env.API_URL || "http://api:3000";
const WEBHOOK_SECRET = process.env.AUTH_WEBHOOK_SECRET || "";

async function notifySignup(user: { id: string; email: string; name?: string }) {
  if (!WEBHOOK_SECRET) {
    console.log("[hook] No AUTH_WEBHOOK_SECRET set, skipping org provisioning");
    return;
  }
  try {
    const res = await fetch(`${API_URL}/api/account/on-signup`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-webhook-secret": WEBHOOK_SECRET,
      },
      body: JSON.stringify({
        user_id: user.id,
        email: user.email,
        name: user.name || null,
      }),
    });
    if (!res.ok) {
      console.error(`[hook] Org provisioning failed: ${res.status} ${await res.text()}`);
    } else {
      const data = await res.json();
      console.log(`[hook] Org provisioned for ${user.email}: ${data.org_id}`);
    }
  } catch (err) {
    console.error("[hook] Failed to notify API:", err);
  }
}

export const auth = betterAuth({
  database: pool,

  // Base path — Caddy proxies /auth/* to this service
  basePath: "/auth",

  emailAndPassword: {
    enabled: true,
    requireEmailVerification: true,
    minPasswordLength: 8,
  },

  socialProviders: Object.keys(socialProviders).length > 0 ? socialProviders : undefined,

  session: {
    expiresIn: 60 * 60 * 24 * 7, // 7 days
    updateAge: 60 * 60 * 24,     // refresh daily
    cookieCache: {
      enabled: true,
      maxAge: 60 * 5, // cache session in cookie for 5 min (reduces DB hits)
    },
  },

  // Trusted origins for CORS — the React SPA
  trustedOrigins: [
    process.env.BETTER_AUTH_URL || "http://localhost:3000",
    "http://localhost:5173", // Vite dev
  ],

  // Rate limiting
  rateLimit: {
    window: 60,   // 1 minute
    max: 10,      // 10 requests per window per IP
  },

  // Email verification — sends magic link
  emailVerification: {
    sendVerificationEmail: async ({ user, url }) => {
      if (process.env.SMTP_HOST) {
        // TODO: integrate nodemailer or Resend SDK
        console.log(`[email] Verification for ${user.email}: ${url}`);
      } else {
        console.log(`[email-dev] Verification link for ${user.email}: ${url}`);
      }
    },
    sendOnSignUp: true,
  },

  // Database hooks — fire webhook after user creation
  databaseHooks: {
    user: {
      create: {
        after: async (user) => {
          // Fire and forget — don't block the signup response
          notifySignup({ id: user.id, email: user.email, name: user.name }).catch(() => {});
        },
      },
    },
  },

  user: {
    additionalFields: {
      onboardingComplete: {
        type: "boolean",
        defaultValue: false,
      },
    },
  },
});

export type Session = typeof auth.$Infer.Session;
