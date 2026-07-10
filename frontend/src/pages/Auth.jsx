import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { signIn, signUp } from "../services/auth";
import "./Auth.css";

export default function Auth() {
  const navigate = useNavigate();

  const [isLogin, setIsLogin] = useState(true);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();

    if (!email || !password) {
      alert("Please fill all fields.");
      return;
    }

    if (!isLogin && password !== confirmPassword) {
      alert("Passwords do not match.");
      return;
    }

    setLoading(true);

    try {
      let result;

      if (isLogin) {
        result = await signIn(email, password);
      } else {
        result = await signUp(email, password);
      }

      if (result.error) {
        alert(result.error.message);
      } else {
        navigate("/dashboard");
      }
    } catch (err) {
      alert(err.message);
    }

    setLoading(false);
  }

  return (
    <div className="auth-container">
      <div className="blob blob1"></div>
      <div className="blob blob2"></div>

      <div className="auth-card">
        <h1>RehabVerse</h1>

        <p className="tagline">
          Every movement brings you closer to recovery.
        </p>

        <form onSubmit={handleSubmit}>
          <div className="input-group">
            <label>Email</label>

            <input
              type="email"
              placeholder="Enter your email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div className="input-group">
            <label>Password</label>

            <input
              type="password"
              placeholder="Enter your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          {!isLogin && (
            <div className="input-group">
              <label>Confirm Password</label>

              <input
                type="password"
                placeholder="Confirm password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
              />
            </div>
          )}

          <button type="submit" disabled={loading}>
            {loading
              ? "Please wait..."
              : isLogin
              ? "Sign In"
              : "Create Account"}
          </button>
        </form>

        <p className="bottom-text">
          {isLogin ? (
            <>
              Don't have an account?{" "}
              <span
                className="toggle-link"
                onClick={() => setIsLogin(false)}
              >
                Create Account
              </span>
            </>
          ) : (
            <>
              Already have an account?{" "}
              <span
                className="toggle-link"
                onClick={() => setIsLogin(true)}
              >
                Sign In
              </span>
            </>
          )}
        </p>
      </div>
    </div>
  );
}