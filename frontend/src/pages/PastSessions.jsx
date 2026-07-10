import { useEffect, useState } from "react";
import { supabase } from "../lib/supabase";
import { useAuth } from "../context/AuthContext";

export default function PastSessions() {

    const { user } = useAuth();

    const [sessions,setSessions]=useState([]);

    useEffect(()=>{

        fetchSessions();

    },[]);

    async function fetchSessions(){

        const {data}=await supabase

        .from("sessions")

        .select("*")

        .eq("user_id",user.id)

        .order("created_at",{ascending:false});

        setSessions(data||[]);

    }

    return(

        <div>

            <h1>Past Sessions</h1>

            {
                sessions.map(session=>(

                    <div key={session.id}>

                        <h3>{session.activity_id}</h3>

                        <p>{session.created_at}</p>

                        <p>{session.metrics.session}</p>

                    </div>

                ))
            }

        </div>

    );

}