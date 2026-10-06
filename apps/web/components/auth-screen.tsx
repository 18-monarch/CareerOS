"use client";
import { useState } from "react";
import { z } from "zod";
import { Compass, ShieldCheck, GitBranch, Check } from "lucide-react";
import { send } from "@/lib/api";
import { Field, Form, Submit, Feedback, useAction } from "./ui";
const schema = z.object({
  email: z.email(),
  password: z.string().min(12).max(128),
  name: z.string().min(1),
});
export default function AuthScreen({ onLogin }: { onLogin: () => void }) {
  const [register, setRegister] = useState(false);
  const action = useAction();
  return (
    <main className="auth-layout">
      <section className="auth-story">
        <div className="brand">
          <Compass size={27} />
          <b>CareerOS</b>
          <span className="version">1.0</span>
        </div>
        <div>
          <p className="eyebrow">YOUR CAREER, WITH INTENTION</p>
          <h1>
            Know your options.
            <br />
            Make your next move.
          </h1>
          <p>
            A private workspace for the opportunities, skills and decisions that
            shape your career.
          </p>
          <div className="auth-points">
            <p>
              <Check size={18} />
              Eligibility grounded in your actual profile
            </p>
            <p>
              <GitBranch size={18} />A clear reason behind every recommendation
            </p>
            <p>
              <ShieldCheck size={18} />
              Your applications and learning, in one place
            </p>
          </div>
        </div>
        <small>
          Personalized Internship, Job, Learning & Career Intelligence
        </small>
      </section>
      <section className="auth-panel">
        <div className="auth-form">
          <p className="eyebrow">LET’S GET TO WORK</p>
          <h2>{register ? "Create your workspace" : "Welcome back"}</h2>
          <p className="muted">
            {register
              ? "Start with your profile. Build from what you know."
              : "Sign in to see what deserves your attention."}
          </p>
          <Form
            onSubmit={(e) => {
              const f = new FormData(e.currentTarget);
              action.run(async () => {
                const body = schema.parse({
                  email: f.get("email"),
                  password: f.get("password"),
                  name: register ? f.get("name") : "CareerOS user",
                });
                await send(`/auth/${register ? "register" : "login"}`, body);
                onLogin();
              });
            }}
          >
            {register && (
              <Field label="Name">
                <input name="name" required autoComplete="name" />
              </Field>
            )}
            <Field label="Email">
              <input
                type="email"
                name="email"
                required
                autoComplete="email"
                placeholder="you@example.com"
              />
            </Field>
            <Field label="Password" hint="At least 12 characters.">
              <input
                type="password"
                name="password"
                required
                minLength={12}
                maxLength={128}
                autoComplete={register ? "new-password" : "current-password"}
              />
            </Field>
            <Feedback {...action} />
            <Submit busy={action.busy}>
              {register ? "Create account" : "Sign in"}
            </Submit>
          </Form>
          <button
            className="text-button auth-switch"
            onClick={() => setRegister(!register)}
          >
            {register
              ? "Already have an account? Sign in"
              : "New here? Create an account"}
          </button>
          <p className="footnote">
            Demo data is opt-in through the seed command. Synthetic
            opportunities are always labeled.
          </p>
        </div>
      </section>
    </main>
  );
}
