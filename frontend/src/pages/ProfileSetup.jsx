import { useState } from "react";
import { supabase } from "../lib/supabase";
import { useAuth } from "../context/AuthContext";

export default function ProfileSetup({ onComplete }) {

    const { user } = useAuth();

    const [fullName, setFullName] = useState("");
    const [age, setAge] = useState("");
    const [gender, setGender] = useState("");

    async function handleSave() {
        console.log("Logged in user:", user.id);

        const { data: allProfiles } = await supabase
            .from("profiles")
            .select("id");

        console.log(allProfiles);
        const { data, error } = await supabase
            .from("profiles")
            .update({
                full_name: fullName,
                age: Number(age),
                gender,
            })
            .eq("id", user.id)
            .select();

        console.log("DATA:", data);
        console.log("ERROR:", error);

        if (error) {
            alert(error.message);
            return;
        }

        onComplete();
    }

    return (
        <div className="profile-overlay">

            <div className="profile-card">

                <h2>Complete Your Profile</h2>

                <p>Let's personalize your recovery journey.</p>

                <input
                    type="text"
                    placeholder="Full Name"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                />

                <input
                    type="number"
                    placeholder="Age"
                    value={age}
                    onChange={(e) => setAge(e.target.value)}
                />

                <select
                    value={gender}
                    onChange={(e) => setGender(e.target.value)}
                >

                    <option value="">Select Gender</option>
                    <option>Male</option>
                    <option>Female</option>
                    <option>Other</option>

                </select>

                <button onClick={handleSave}>
                    Continue
                </button>

            </div>

        </div>
    );
}