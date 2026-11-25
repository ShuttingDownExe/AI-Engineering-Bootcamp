export function SessionList({sessions, selectedSessionID, onSelectSession}){
    return (
        <div className="session-list">
            {sessions.map(session => (
                <button 
                key={session.id}
                onClick={() => onSelectSession(session.id)}
                aria-pressed={session === selectedSessionID}
                >
                    {session.name}
                </button>
            ))}
        </div>
    )
}

export function SessionCreate({onSelectSession}) {
    
    return (
        <button onClick={onSelectSession}>
            +
        </button>
    )
}