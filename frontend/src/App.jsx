import { Routes, Route, Navigate } from "react-router-dom";

import Auth from "./pages/Auth";
import { Dashboard } from "./Dashboard";

import { useAuth } from "./context/AuthContext";
import PastSessions from "./pages/PastSessions";

function App() {
    const { user, loading } = useAuth();

    if (loading) return <h2>Loading...</h2>;

    console.log(user);
    return (
        <Routes>
            {!user ? (
                <>
                    <Route path="/" element={<Auth />} />
                    <Route path="*" element={<Navigate to="/" replace />} />
                </>
            ) : (
                <>
                    <Route path="/dashboard" element={<Dashboard />} />
                    <Route path="/sessions" element={<PastSessions />} />
                    <Route path="*" element={<Navigate to="/dashboard" replace />} />
                </>
            )}
        </Routes>
    );
}

export default App;