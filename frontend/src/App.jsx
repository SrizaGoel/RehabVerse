// import './App.css'
// import { Dashboard } from './Dashboard'

// function App() {
//   return (
//     <>
//       <Dashboard />
//     </>
//   )
// }

// export default App

import { Routes, Route, Navigate } from "react-router-dom";

import Login from "./pages/Login";
import Signup from "./pages/Signup";
import { Dashboard } from "./Dashboard";

import { useAuth } from "./context/AuthContext";

function App() {

    const { user, loading } = useAuth();

    if (loading)
        return <h2>Loading...</h2>;

    return (

        <Routes>

            <Route
                path="/login"
                element={<Login />}
            />

            <Route
                path="/signup"
                element={<Signup />}
            />

            <Route
                path="/"
                element={
                    user
                        ? <Dashboard />
                        : <Navigate to="/login" />
                }
            />

        </Routes>

    );

}

export default App;