import { Link } from "react-router-dom";

export default function LoginPage() {
  return (
    <div className="centered monitor">
      <svg className="ecg-bg" aria-hidden="true">
        <defs>
          <pattern id="beat" width="240" height="120" patternUnits="userSpaceOnUse">
            <polyline points="0,60 60,60 70,60 78,30 88,95 96,50 104,60 150,60 160,60 168,35 176,85 184,60 240,60" />
          </pattern>
        </defs>
        <rect width="100%" height="120" fill="url(#beat)" />
      </svg>
      <form className="login" onSubmit={(e) => e.preventDefault()}>
        <svg className="trace" viewBox="0 0 240 40" aria-hidden="true">
          <polyline points="0,22 60,22 70,22 78,6 88,36 96,16 104,22 150,22 160,22 168,10 176,32 184,22 240,22" />
        </svg>
        <h1>Sign in to RPM</h1>
        <label htmlFor="email">Email</label>
        <input id="email" type="email" autoComplete="username" />
        <label htmlFor="password">Password</label>
        <input id="password" type="password" autoComplete="current-password" />
        <button type="submit" className="btn">Sign in</button>
        <p className="temp">
          Temporary: <Link to="/admin">admin area</Link> · <Link to="/clinician">clinician area</Link>
        </p>
      </form>
    </div>
  );
}